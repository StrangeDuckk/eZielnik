using System.Globalization;
using HerbRecognition_Web.Components.Shared;

namespace HerbRecognition_Web.Communication.Services
{
    /// <summary>Wspólne pomocniki filtrów bibliotek roślin i przepisów.</summary>
    public static class LibraryFilter
    {
        private static readonly CultureInfo Polish = new("pl-PL");
        private static readonly StringComparer PolishOrder = StringComparer.Create(Polish, ignoreCase: true);

        /// <summary>
        /// Opcje listy z wartości kafelków: każda wartość raz, z liczbą kafelków, alfabetycznie.
        /// valuesPerItem – wartości jednego kafelka (np. wszystkie jego choroby).
        /// </summary>
        public static List<FilterSelect.Option> OptionsMany<T>(
            IEnumerable<T> items,
            Func<T, IEnumerable<string?>> valuesPerItem,
            Func<string, int>? order = null)
        {
            var counts = new Dictionary<string, int>(PolishOrder);

            foreach (var item in items)
            {
                // ta sama wartość dwa razy na jednym kafelku liczy się raz
                foreach (var value in valuesPerItem(item)
                             .Where(v => !string.IsNullOrWhiteSpace(v))
                             .Select(v => v!.Trim())
                             .Distinct(PolishOrder))
                {
                    counts[value] = counts.GetValueOrDefault(value) + 1;
                }
            }

            var sorted = order is null
                ? counts.OrderBy(c => c.Key, PolishOrder)
                : counts.OrderBy(c => order(c.Key)).ThenBy(c => c.Key, PolishOrder);

            return sorted.Select(c => new FilterSelect.Option(c.Key, c.Key, c.Value)).ToList();
        }

        /// <summary>Jedna wartość na kafelek (np. typ rośliny).</summary>
        public static List<FilterSelect.Option> Options<T>(
            IEnumerable<T> items,
            Func<T, string?> valuePerItem,
            Func<string, int>? order = null) =>
            OptionsMany(items, x => new[] { valuePerItem(x) }, order);

        /// <summary>Czy wartość pasuje do filtra (null = filtr wyłączony).</summary>
        public static bool Is(string? wanted, string? actual) =>
            wanted is null || (actual is not null && PolishOrder.Equals(wanted, actual.Trim()));

        /// <summary>Czy kafelek ma wartość z filtra (null = filtr wyłączony).</summary>
        public static bool Has(string? wanted, IEnumerable<string?> actual) =>
            wanted is null || actual.Any(a => a is not null && PolishOrder.Equals(wanted, a.Trim()));

        public static bool Same(string a, string b) => PolishOrder.Equals(a, b);

        // ------------------------------------------------------------------
        //  Miesiące zbioru – w kolejności kalendarza, nie alfabetu
        // ------------------------------------------------------------------

        private static readonly string[] MonthStems =
        {
            "stycz", "lut", "marz", "kwie", "maj", "czerw",
            "lip", "sierp", "wrze", "paźdz", "listop", "grud"
        };

        /// <summary>Numer pierwszego miesiąca w nazwie (np. "maj–czerwiec" = 5); bez miesiąca na końcu.</summary>
        public static int MonthOrder(string name)
        {
            var text = name.ToLower(Polish);
            var best = int.MaxValue;
            var bestPosition = int.MaxValue;

            for (var i = 0; i < MonthStems.Length; i++)
            {
                var position = text.IndexOf(MonthStems[i], StringComparison.Ordinal);
                if (position >= 0 && position < bestPosition)
                {
                    bestPosition = position;
                    best = i + 1;
                }
            }

            return best;
        }

        // ------------------------------------------------------------------
        //  Trujące / bezpieczne
        // ------------------------------------------------------------------

        public const string Poisonous = "poisonous";
        public const string Safe = "safe";

        public static readonly IReadOnlyList<FilterSelect.Option> PoisonOptions = new[]
        {
            new FilterSelect.Option(Safe, "Bezpieczne (nietrujące)"),
            new FilterSelect.Option(Poisonous, "Trujące")
        };

        // objawy zatrucia: od bólu brzucha / nudności w górę aż do śmierci
        private static readonly string[] PoisonWords =
        {
            "nudno", "wymiot", "biegunk", "brzuch", "zatru", "toksycz", "trując", "trujac",
            "zawrot", "duszno", "oddech", "oddych", "narząd", "narzad", "nerek", "wątrob", "watrob",
            "serc", "parali", "drgawk", "śmier", "smier", "zgon",
            "nausea", "vomit", "diarr", "stomach", "toxic", "poison", "dizz", "breath",
            "organ damage", "organs", "paraly", "death", "fatal"
        };

        // tylko podrażnienie / uczulenie – to ostrzeżenie, nie "trująca"
        private static readonly string[] IrritationWords =
        {
            "alerg", "uczul", "podrażn", "podrazn", "irritat", "allerg"
        };

        /// <summary>
        /// Czy pokazać "☠ Trująca". Reguła:
        /// - brak wpisu = nietrująca,
        /// - opis objawów zatrucia (ból brzucha, nudności, wymioty … aż do śmierci) = trująca,
        /// - samo podrażnienie / reakcja alergiczna = nie (szczegóły są w ostrzeżeniu na stronie rośliny),
        /// - opis, którego nie rozpoznajemy = trująca (bezpieczniej ostrzec niż przemilczeć).
        /// </summary>
        public static bool IsPoisonous(string? poisonabilityDescription)
        {
            if (string.IsNullOrWhiteSpace(poisonabilityDescription)) return false;

            var text = poisonabilityDescription.ToLower(Polish);

            if (text.Contains("nietruj") || text.Contains("bezpieczn") || text.StartsWith("brak"))
                return false;

            if (PoisonWords.Any(text.Contains))
                return true;

            return !IrritationWords.Any(text.Contains);
        }

        public static bool MatchesPoison(string? wanted, bool isPoisonous) => wanted switch
        {
            Poisonous => isPoisonous,
            Safe => !isPoisonous,
            _ => true
        };
    }
}
