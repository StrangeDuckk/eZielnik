namespace HerbRecognition_Web.Communication.DTOs
{
    /// <summary>Wynik rozpoznawania ze zdjęcia (POST api/recognize) – opis pól w API.</summary>
    public class RecognitionResultDTO
    {
        public RecognitionPlantDTO? Final { get; set; }

        /// <summary>agreed, majority, single, uncertain, none</summary>
        public string Status { get; set; } = "none";

        public int VotesForFinal { get; set; }
        public int SupportCount { get; set; }
        public int VotesTotal { get; set; }
        public double Confidence { get; set; }

        public List<RecognitionVoteDTO> Votes { get; set; } = new();
        public PlantSearchCriteriaDTO? FilledForm { get; set; }
        public List<RecognitionFieldDTO> FilledFields { get; set; } = new();
        public List<string> Notes { get; set; } = new();
        public int DurationMs { get; set; }
    }

    public class RecognitionPlantDTO
    {
        public int? PlantId { get; set; }
        public string LatinName { get; set; } = "";
        public string? PolishName { get; set; }
        public string? PlantTypeName { get; set; }
        public string? PoisonabilityDescription { get; set; }
        public string? ThumbnailUrl { get; set; }
        public bool InDatabase { get; set; }

        /// <summary>Nazwa do nagłówka: polska, a gdy rośliny nie ma w bazie – łacińska.</summary>
        public string DisplayName => string.IsNullOrWhiteSpace(PolishName) ? LatinName : PolishName;
    }

    public class RecognitionVoteDTO
    {
        public string Source { get; set; } = "";
        public string ModelName { get; set; } = "";
        public string Method { get; set; } = "";
        public bool Voted { get; set; }
        public string? AbstainReason { get; set; }
        public RecognitionPlantDTO? Choice { get; set; }
        public double Confidence { get; set; }
        public bool AgreesWithFinal { get; set; }
        public List<RecognitionAlternativeDTO> Alternatives { get; set; } = new();
        public int TiedCount { get; set; }
    }

    public class RecognitionAlternativeDTO
    {
        public RecognitionPlantDTO Plant { get; set; } = new();
        public double Confidence { get; set; }
    }

    public class RecognitionFieldDTO
    {
        public string Part { get; set; } = "";
        public string Field { get; set; } = "";
        public string Value { get; set; } = "";
        public double Confidence { get; set; }
        public bool Accepted { get; set; }
    }
}
