namespace HerbRecognition_APIs.DTOs
{
    // =====================================================================
    //  Wynik rozpoznawania zwracany stronie (POST api/recognize)
    // =====================================================================

    public class RecognitionResultDTO
    {
        /// <summary>Roślina wybrana w głosowaniu. Null = żaden model nie oddał głosu.</summary>
        public RecognitionPlantDTO? Final { get; set; }

        /// <summary>agreed (wszystkie głosy zgodne), majority (większość), single (jeden pewny głos), uncertain, none.</summary>
        public string Status { get; set; } = "none";

        /// <summary>Ile modeli miało wynik na pierwszym miejscu.</summary>
        public int VotesForFinal { get; set; }

        /// <summary>Ile modeli miało wynik gdziekolwiek w swoich typach.</summary>
        public int SupportCount { get; set; }

        /// <summary>Ile modeli oddało głos.</summary>
        public int VotesTotal { get; set; }

        /// <summary>0–1: jaka część wszystkich głosów (ważonych pewnością) poparła wynik.</summary>
        public double Confidence { get; set; }

        /// <summary>Typy poszczególnych modeli (zawsze trzy, także te, które nie głosowały).</summary>
        public List<RecognitionVoteDTO> Votes { get; set; } = new();

        /// <summary>Formularz wypełniony przez BioCLIP – strona może go otworzyć w wyszukiwarce.</summary>
        public PlantSearchCriteriaDTO? FilledForm { get; set; }

        /// <summary>Cechy odczytane ze zdjęcia (także te odrzucone jako niepewne).</summary>
        public List<RecognitionFieldDTO> FilledFields { get; set; } = new();

        public List<string> Notes { get; set; } = new();

        public int DurationMs { get; set; }
    }

    public class RecognitionPlantDTO
    {
        public int? PlantId { get; set; }               // null = roślina spoza bazy
        public string LatinName { get; set; } = "";
        public string? PolishName { get; set; }
        public string? PlantTypeName { get; set; }
        public string? PoisonabilityDescription { get; set; }
        public string? ThumbnailUrl { get; set; }
        public bool InDatabase => PlantId is not null;
    }

    public class RecognitionVoteDTO
    {
        /// <summary>bioclip-photo, bioclip-form, plantclef-photo</summary>
        public string Source { get; set; } = "";
        public string ModelName { get; set; } = "";
        public string Method { get; set; } = "";

        public bool Voted { get; set; }
        public string? AbstainReason { get; set; }

        public RecognitionPlantDTO? Choice { get; set; }
        public double Confidence { get; set; }
        public bool AgreesWithFinal { get; set; }

        /// <summary>Kolejne typy tego modelu (bez pierwszego).</summary>
        public List<RecognitionAlternativeDTO> Alternatives { get; set; } = new();

        /// <summary>Tylko dla wyszukiwania formularzem: ile roślin miało ten sam najlepszy wynik.</summary>
        public int TiedCount { get; set; }
    }

    public class RecognitionAlternativeDTO
    {
        public RecognitionPlantDTO Plant { get; set; } = new();
        public double Confidence { get; set; }
    }

    public class RecognitionFieldDTO
    {
        public string Part { get; set; } = "";      // Roślina, Liść, Kwiat, Owoc, Kapelusz, Pień
        public string Field { get; set; } = "";     // typ, kolor, kształt, powierzchnia, plamki
        public string Value { get; set; } = "";
        public double Confidence { get; set; }
        public bool Accepted { get; set; }
    }

    // =====================================================================
    //  Odpowiedź serwisu ml (HerbRecognition_ML, POST /analyze)
    // =====================================================================

    public class MlAnalyzeResponse
    {
        public MlModelResult? Bioclip { get; set; }
        public MlModelResult? Plantclef { get; set; }
        public MlForm? Form { get; set; }
        public Dictionary<string, int>? TimingsMs { get; set; }
    }

    public class MlModelResult
    {
        public string Model { get; set; } = "";
        public List<MlCandidate> Candidates { get; set; } = new();
    }

    public class MlCandidate
    {
        public string Latin { get; set; } = "";
        public string Key { get; set; } = "";
        public double Score { get; set; }
        public int? DbId { get; set; }
    }

    public class MlForm
    {
        public Dictionary<string, double>? Organs { get; set; }
        public List<string>? VisibleParts { get; set; }
        public List<MlField> Fields { get; set; } = new();
    }

    public class MlField
    {
        public string Part { get; set; } = "";
        public string Field { get; set; } = "";
        public int? Id { get; set; }
        public bool? Value { get; set; }
        public string Name { get; set; } = "";
        public double Score { get; set; }
        public bool Accepted { get; set; }
    }
}
