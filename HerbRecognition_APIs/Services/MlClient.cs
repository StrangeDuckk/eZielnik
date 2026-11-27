using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;
using HerbRecognition_APIs.DTOs;

namespace HerbRecognition_APIs.Services
{
    /// <summary>Rozpoznawanie chwilowo niedostępne (serwis ml wyłączony albo jeszcze się uruchamia).</summary>
    public class RecognitionUnavailableException(string message) : Exception(message);

    /// <summary>
    /// Połączenie z serwisem rozpoznawania HerbRecognition_ML (sieć wewnętrzna Dockera).
    /// Adres: Recognition:MlBaseUrl (na serwerze http://ml:8000/).
    /// </summary>
    public class MlClient(HttpClient http, ILogger<MlClient> logger)
    {
        public async Task<MlAnalyzeResponse> AnalyzeAsync(byte[] image, object request, CancellationToken ct)
        {
            if (http.BaseAddress is null)
                throw new RecognitionUnavailableException("Rozpoznawanie ze zdjęcia nie jest skonfigurowane.");

            using var content = new MultipartFormDataContent();

            var file = new ByteArrayContent(image);
            file.Headers.ContentType = new MediaTypeHeaderValue("image/jpeg");
            content.Add(file, "image", "photo.jpg");
            content.Add(new StringContent(JsonSerializer.Serialize(request, JsonOptions)), "request");

            HttpResponseMessage response;
            try
            {
                response = await http.PostAsync("analyze", content, ct);
            }
            catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException && !ct.IsCancellationRequested)
            {
                logger.LogWarning(ex, "Serwis ml nie odpowiada");
                throw new RecognitionUnavailableException(
                    "Rozpoznawanie ze zdjęcia jest chwilowo niedostępne. Spróbuj ponownie za kilka minut.");
            }

            using (response)
            {
                if (response.StatusCode == HttpStatusCode.ServiceUnavailable)
                    throw new RecognitionUnavailableException(
                        "Modele rozpoznawania właśnie się uruchamiają (po wdrożeniu trwa to do kilku minut). " +
                        "Spróbuj ponownie za chwilę.");

                if (response.StatusCode == HttpStatusCode.BadRequest)
                    throw new ArgumentException("Nie udało się odczytać zdjęcia. Wybierz plik JPEG, PNG lub WebP.");

                if (!response.IsSuccessStatusCode)
                {
                    var body = await response.Content.ReadAsStringAsync(ct);
                    logger.LogError("Serwis ml zwrócił {Status}: {Body}", (int)response.StatusCode, body);
                    throw new RecognitionUnavailableException("Rozpoznawanie się nie powiodło. Spróbuj ponownie.");
                }

                return await response.Content.ReadFromJsonAsync<MlAnalyzeResponse>(JsonOptions, ct)
                       ?? throw new RecognitionUnavailableException("Serwis rozpoznawania zwrócił pustą odpowiedź.");
            }
        }

        private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);
    }
}
