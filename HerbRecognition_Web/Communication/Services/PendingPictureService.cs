namespace HerbRecognition_Web.Communication.Services
{
    /// <summary>
    /// Miniatury zgłoszeń (rośliny i przepisy) – tylko dla zalogowanego admina.
    /// Publiczne listy zgłoszeń celowo nie mają zdjęć (nie były sprawdzone),
    /// ale admin i tak je widzi w panelu, więc na kafelkach dostaje podgląd pierwszego zdjęcia.
    /// Bierzemy je z list panelu admina (api/admin/userinputs, api/admin/productinputs) – bez zmian w API.
    /// </summary>
    public class PendingPictureService(AdminAuthService auth, AdminApiService admin, AdminProductApiService adminProducts)
    {
        /// <summary>Id zgłoszenia rośliny -> adres miniatury. Pusty słownik dla niezalogowanych.</summary>
        public async Task<Dictionary<int, string>> PlantSubmissionThumbnailsAsync()
        {
            if (!auth.IsLoggedIn) return new();

            try
            {
                var items = await admin.GetSubmissionsAsync();
                return items
                    .Select(i => (i.Id, Url: SafeUrl.Image(i.MainThumbnailUrl)))
                    .Where(x => x.Url is not null)
                    .ToDictionary(x => x.Id, x => x.Url!);
            }
            catch (Exception ex)
            {
                // wygasła sesja albo błąd API – kafelki zostają bez zdjęć, strona działa dalej
                Console.Error.WriteLine($"Nie udało się pobrać miniatur zgłoszeń roślin: {ex.Message}");
                return new();
            }
        }

        /// <summary>Id zgłoszenia przepisu -> adres miniatury. Pusty słownik dla niezalogowanych.</summary>
        public async Task<Dictionary<int, string>> ProductSubmissionThumbnailsAsync()
        {
            if (!auth.IsLoggedIn) return new();

            try
            {
                var items = await adminProducts.GetSubmissionsAsync();
                return items
                    .Select(i => (i.Id, Url: SafeUrl.Image(i.MainThumbnailUrl)))
                    .Where(x => x.Url is not null)
                    .ToDictionary(x => x.Id, x => x.Url!);
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"Nie udało się pobrać miniatur zgłoszeń przepisów: {ex.Message}");
                return new();
            }
        }

        /// <summary>Wstawia miniatury do zgłoszeń przepisów (ProductCard pokazuje MainThumbnailUrl).</summary>
        public async Task ApplyToProductSubmissionsAsync(IEnumerable<Communication.DTOs.ProductPreviewDTO> pending)
        {
            var list = pending.ToList();
            if (list.Count == 0 || !auth.IsLoggedIn) return;

            var thumbnails = await ProductSubmissionThumbnailsAsync();
            foreach (var item in list)
                if (thumbnails.TryGetValue(item.Id, out var url))
                    item.MainThumbnailUrl = url;
        }
    }
}
