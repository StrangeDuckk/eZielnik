namespace HerbRecognition_Web.Communication.DTOs
{
    /// <summary>
    /// Dane kafelka rośliny – ten sam kafelek w bibliotece (/plants) i w wynikach wyszukiwania po nazwie (/search).
    /// Id = Id rośliny albo, dla zgłoszenia (IsPending), Id zgłoszenia z userinput.
    /// </summary>
    public sealed record PlantCardItem(
        int Id,
        string PolishName,
        string? LatinName,
        string? PlantTypeName,
        string? MonthOfHarvestName,
        string? OccuranceName,
        bool IsPoisonous,
        string? ThumbnailUrl,
        bool IsPending);
}
