using System.Diagnostics;
using HerbRecognition_APIs.DTOs;
using HerbRecognition_APIs.Models;
using Microsoft.EntityFrameworkCore;

namespace HerbRecognition_APIs.Services
{
    public interface IRecognitionService
    {
        Task<RecognitionResultDTO> RecognizeAsync(byte[] image, CancellationToken ct);
    }

    /// <summary>
    /// Rozpoznawanie rośliny ze zdjęcia – trzy głosy i głosowanie.
    ///
    ///   1. BioCLIP, zdjęcie      – model porównuje zdjęcie z nazwami gatunków,
    ///   2. BioCLIP, formularz    – model wypełnia formularz cech, a wyszukiwarka
    ///                              eZielnika (PlantSearchService) wskazuje najlepiej pasującą roślinę z bazy,
    ///   3. PlantCLEF, zdjęcie    – klasyfikator Pl@ntNet wskazuje gatunek.
    ///
    /// Głosowanie jest "miękkie": każdy model dzieli swój głos między kilka gatunków
    /// według swojej pewności (np. 0,7 na miętę i 0,2 na melisę), a głosy są mnożone
    /// przez wagę modelu. Wygrywa gatunek z największą sumą.
    /// </summary>
    public class RecognitionService(
        HerbRecognitionDbContext data,
        IPlantSearchService plantSearch,
        IPictureService pictures,
        MlClient ml) : IRecognitionService
    {
        // wagi głosów: zdjęcie liczy się bardziej niż formularz, bo formularz widzi tylko kilka cech
        private const double WeightBioclipPhoto = 1.0;
        private const double WeightBioclipForm = 0.6;
        private const double WeightPlantclef = 1.0;

        private const int MinFormFields = 2;          // mniej pewnych cech = formularz nie głosuje
        private const int MinFormMatchPercent = 40;   // słabsze dopasowanie = formularz nie głosuje
        private const double UncertainBelow = 0.35;   // poniżej tej pewności wynik jest "niepewny"

        public const string SourceBioclipPhoto = "bioclip-photo";
        public const string SourceBioclipForm = "bioclip-form";
        public const string SourcePlantclef = "plantclef-photo";

        public async Task<RecognitionResultDTO> RecognizeAsync(byte[] image, CancellationToken ct)
        {
            var stopwatch = Stopwatch.StartNew();

            // ---------- dane z bazy potrzebne modelom ----------
            var plants = await data.Plants
                .AsNoTracking()
                .Select(p => new PlantInfo(
                    p.Id, p.Polishname, p.Latinname, p.Planttype.Name,
                    p.Poisonability != null ? p.Poisonability.Description : null))
                .ToListAsync(ct);

            var plantTypes = await data.Planttypes.AsNoTracking()
                .Select(t => new { t.Id, Name = t.Name }).ToListAsync(ct);

            var request = new
            {
                dbPlants = plants.Where(p => !string.IsNullOrWhiteSpace(p.Latin))
                                 .Select(p => new { id = p.Id, latin = p.Latin }),
                dictionaries = new
                {
                    plantTypes = plantTypes.Select(t => new { id = t.Id, name = t.Name }),
                    colors = await data.Colors.AsNoTracking()
                        .Select(c => new { id = c.Id, name = c.ColorName }).ToListAsync(ct),
                    shapes = await data.Shapes.AsNoTracking()
                        .Select(s => new { id = s.Id, name = s.ShapeName }).ToListAsync(ct),
                    surfaces = await data.Surfaces.AsNoTracking()
                        .Select(s => new { id = s.Id, name = s.SurfaceName }).ToListAsync(ct)
                }
            };

            // ---------- modele ----------
            var analysis = await ml.AnalyzeAsync(image, request, ct);

            var thumbnails = await pictures.GetPlantMainThumbnailsAsync();
            var byId = plants.ToDictionary(p => p.Id);

            RecognitionPlantDTO ToPlant(MlCandidate c) =>
                c.DbId is int id && byId.TryGetValue(id, out var p)
                    ? new RecognitionPlantDTO
                    {
                        PlantId = p.Id,
                        LatinName = p.Latin ?? c.Latin,
                        PolishName = p.Polish,
                        PlantTypeName = p.TypeName,
                        PoisonabilityDescription = p.Poison,
                        ThumbnailUrl = thumbnails.GetValueOrDefault(p.Id)
                    }
                    : new RecognitionPlantDTO { LatinName = c.Latin };

            RecognitionPlantDTO FromDb(int id) =>
                ToPlant(new MlCandidate { DbId = id, Latin = byId.GetValueOrDefault(id)?.Latin ?? "" });

            var result = new RecognitionResultDTO();
            var ballots = new List<Ballot>();

            // ---------- głos 1: BioCLIP, zdjęcie ----------
            var bioclipVote = ImageVote(SourceBioclipPhoto, "BioCLIP", "Rozpoznanie ze zdjęcia",
                analysis.Bioclip, WeightBioclipPhoto, ToPlant, ballots, abstainReason: null);

            // ---------- głos 2: BioCLIP, formularz -> wyszukiwarka ----------
            var fields = analysis.Form?.Fields ?? new();
            var criteria = BuildCriteria(fields);
            result.FilledFields = fields.Select(DescribeField).ToList();

            var formVote = new RecognitionVoteDTO
            {
                Source = SourceBioclipForm,
                ModelName = "BioCLIP",
                Method = "Wypełniony formularz + wyszukiwarka eZielnika"
            };

            var acceptedCount = fields.Count(f => f.Accepted);
            if (acceptedCount < MinFormFields)
            {
                formVote.AbstainReason = "Model rozpoznał za mało cech, żeby wyszukać roślinę.";
            }
            else
            {
                result.FilledForm = criteria;
                var search = await plantSearch.SearchAsync(criteria);
                var top = search.Results.FirstOrDefault();

                if (top is null || top.MatchPercent < MinFormMatchPercent)
                {
                    formVote.AbstainReason = "Żadna roślina z bazy nie pasuje do odczytanych cech.";
                }
                else
                {
                    var tied = search.Results.Where(r => r.MatchPercent == top.MatchPercent).ToList();
                    var share = top.MatchPercent / 100.0 / tied.Count;

                    formVote.Voted = true;
                    formVote.Choice = FromDb(top.Id);
                    formVote.Confidence = top.MatchPercent / 100.0;
                    formVote.TiedCount = tied.Count;
                    formVote.Alternatives = search.Results.Skip(1).Take(3)
                        .Select(r => new RecognitionAlternativeDTO { Plant = FromDb(r.Id), Confidence = r.MatchPercent / 100.0 })
                        .ToList();

                    foreach (var r in tied)
                        ballots.Add(new Ballot(SourceBioclipForm, $"db:{r.Id}", WeightBioclipForm * share, r.Id == top.Id));
                }
            }

            // ---------- głos 3: PlantCLEF, zdjęcie ----------
            var isFungus = fields.Any(f => f.Accepted && f.Part == "plant" && f.Field == "type"
                                           && f.Name.Trim().Equals("Grzyb", StringComparison.OrdinalIgnoreCase));

            var plantclefVote = ImageVote(SourcePlantclef, "PlantCLEF 2024 (Pl@ntNet)", "Rozpoznanie ze zdjęcia",
                analysis.Plantclef, WeightPlantclef, ToPlant, ballots,
                abstainReason: analysis.Plantclef is null
                    ? "Model jest niedostępny na serwerze."
                    : isFungus ? "Ten model rozpoznaje tylko rośliny – na zdjęciu jest grzyb." : null);

            if (analysis.Plantclef is null)
                result.Notes.Add("Model PlantCLEF jest niedostępny – głosują tylko dwa typy BioCLIP.");

            result.Votes = [bioclipVote, formVote, plantclefVote];

            // ---------- głosowanie ----------
            Decide(result, ballots, ToPlant, FromDb, analysis);

            result.DurationMs = (int)stopwatch.ElapsedMilliseconds;
            return result;
        }

        // =====================================================================
        //  Głos modelu "ze zdjęcia" (lista gatunków z prawdopodobieństwem)
        // =====================================================================

        private static RecognitionVoteDTO ImageVote(
            string source, string modelName, string method, MlModelResult? model, double weight,
            Func<MlCandidate, RecognitionPlantDTO> toPlant, List<Ballot> ballots, string? abstainReason)
        {
            var vote = new RecognitionVoteDTO { Source = source, ModelName = modelName, Method = method };
            var candidates = model?.Candidates ?? new();

            if (candidates.Count > 0)
            {
                vote.Choice = toPlant(candidates[0]);
                vote.Confidence = candidates[0].Score;
                vote.Alternatives = candidates.Skip(1).Take(3)
                    .Select(c => new RecognitionAlternativeDTO { Plant = toPlant(c), Confidence = c.Score })
                    .ToList();
            }

            if (abstainReason is not null)
            {
                vote.AbstainReason = abstainReason;
                return vote;   // typ pokazujemy, ale nie liczy się do głosowania
            }

            if (candidates.Count == 0)
            {
                vote.AbstainReason = "Model nie zwrócił wyniku.";
                return vote;
            }

            vote.Voted = true;
            for (var i = 0; i < candidates.Count; i++)
                ballots.Add(new Ballot(source, KeyOf(candidates[i]), weight * candidates[i].Score, i == 0));

            return vote;
        }

        // =====================================================================
        //  Wynik głosowania
        // =====================================================================

        private static void Decide(
            RecognitionResultDTO result, List<Ballot> ballots,
            Func<MlCandidate, RecognitionPlantDTO> toPlant, Func<int, RecognitionPlantDTO> fromDb,
            MlAnalyzeResponse analysis)
        {
            var voting = result.Votes.Where(v => v.Voted).ToList();
            result.VotesTotal = voting.Count;

            if (ballots.Count == 0)
            {
                result.Status = "none";
                return;
            }

            var winner = ballots
                .GroupBy(b => b.Key)
                .Select(g => new { Key = g.Key, Score = g.Sum(b => b.Score) })
                .OrderByDescending(x => x.Score)
                .First();

            var totalWeight = voting.Sum(v => v.Source switch
            {
                SourceBioclipForm => WeightBioclipForm,
                SourcePlantclef => WeightPlantclef,
                _ => WeightBioclipPhoto
            });

            result.Confidence = totalWeight > 0 ? Math.Min(1, winner.Score / totalWeight) : 0;
            result.Final = winner.Key.StartsWith("db:")
                ? fromDb(int.Parse(winner.Key[3..]))
                : toPlant(FindCandidate(winner.Key, analysis) ?? new MlCandidate { Latin = winner.Key });

            // który model miał zwycięzcę na pierwszym miejscu
            foreach (var vote in voting)
            {
                vote.AgreesWithFinal = ballots.Any(b => b.Source == vote.Source && b.IsTopChoice && b.Key == winner.Key);
            }

            result.VotesForFinal = voting.Count(v => v.AgreesWithFinal);
            result.SupportCount = voting.Count(v => ballots.Any(b => b.Source == v.Source && b.Key == winner.Key));

            result.Status =
                result.VotesForFinal == result.VotesTotal && result.VotesTotal >= 2 ? "agreed" :
                result.VotesForFinal >= 2 ? "majority" :
                result.Confidence >= UncertainBelow && result.VotesForFinal == 1 ? "single" :
                "uncertain";
        }

        private static MlCandidate? FindCandidate(string key, MlAnalyzeResponse analysis) =>
            (analysis.Bioclip?.Candidates ?? new())
                .Concat(analysis.Plantclef?.Candidates ?? new())
                .FirstOrDefault(c => KeyOf(c) == key);

        private static string KeyOf(MlCandidate c) => c.DbId is int id ? $"db:{id}" : $"name:{c.Key}";

        // =====================================================================
        //  Formularz z cech odczytanych przez BioCLIP
        // =====================================================================

        private static PlantSearchCriteriaDTO BuildCriteria(List<MlField> fields)
        {
            var c = new PlantSearchCriteriaDTO { MinMatchPercent = 0, IncludePending = false };

            foreach (var f in fields.Where(f => f.Accepted))
            {
                if (f.Part == "plant")
                {
                    if (f.Field == "type") c.PlantTypeId = f.Id;
                    continue;
                }

                var part = f.Part switch
                {
                    "leaf" => c.Leaf ??= new PartCriteriaDTO(),
                    "flower" => c.Flower ??= new PartCriteriaDTO(),
                    "fruit" => c.Fruit ??= new PartCriteriaDTO(),
                    "hat" => c.Hat ??= new PartCriteriaDTO(),
                    "stalk" => c.Stalk ??= new PartCriteriaDTO(),
                    _ => null
                };

                if (part is null) continue;

                switch (f.Field)
                {
                    case "color": part.ColorId = f.Id; break;
                    case "shape": part.ShapeId = f.Id; break;
                    case "surface": part.SurfaceId = f.Id; break;
                    case "hasSpots": part.HasSpots = f.Value; break;
                }
            }

            return c;
        }

        private static RecognitionFieldDTO DescribeField(MlField f) => new()
        {
            Part = f.Part switch
            {
                "plant" => "Roślina",
                "leaf" => "Liść",
                "flower" => "Kwiat",
                "fruit" => "Owoc",
                "hat" => "Kapelusz",
                "stalk" => "Pień",
                _ => f.Part
            },
            Field = f.Field switch
            {
                "type" => "typ",
                "color" => "kolor",
                "shape" => "kształt",
                "surface" => "powierzchnia",
                "hasSpots" => "plamki",
                _ => f.Field
            },
            Value = f.Name,
            Confidence = f.Score,
            Accepted = f.Accepted
        };

        private sealed record PlantInfo(int Id, string Polish, string? Latin, string? TypeName, string? Poison);

        /// <summary>Część głosu jednego modelu oddana na jeden gatunek.</summary>
        private sealed record Ballot(string Source, string Key, double Score, bool IsTopChoice);
    }
}
