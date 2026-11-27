using System.Net;
using System.Net.Http.Headers;
using HerbRecognition_Web.Communication.DTOs;

namespace HerbRecognition_Web.Communication.Services
{
    public class RecognitionApiException(string message) : Exception(message);

    /// <summary>Rozpoznawanie rośliny ze zdjęcia (API -> serwis ml).</summary>
    public class RecognitionApiService(HttpClient http)
    {
        public async Task<RecognitionResultDTO> RecognizeAsync(PhotoUpload photo, CancellationToken ct = default)
        {
            using var content = new MultipartFormDataContent();

            var file = new ByteArrayContent(photo.Data);
            file.Headers.ContentType = new MediaTypeHeaderValue("image/jpeg");
            content.Add(file, "photo", photo.FileName);

            HttpResponseMessage response;
            try
            {
                response = await http.PostAsync("api/recognize", content, ct);
            }
            catch (TaskCanceledException) when (!ct.IsCancellationRequested)
            {
                throw new RecognitionApiException("Rozpoznawanie trwało za długo. Spróbuj ponownie za chwilę.");
            }
            catch (HttpRequestException)
            {
                throw new RecognitionApiException("Nie udało się połączyć z serwerem. Spróbuj ponownie.");
            }

            using (response)
            {
                if (response.IsSuccessStatusCode)
                {
                    return await response.Content.ReadFromJsonAsync<RecognitionResultDTO>(ct)
                           ?? throw new RecognitionApiException("Serwer zwrócił pusty wynik.");
                }

                if (response.StatusCode == HttpStatusCode.TooManyRequests)
                    throw new RecognitionApiException("Dużo osób rozpoznaje teraz rośliny. Spróbuj ponownie za minutę.");

                var body = (await response.Content.ReadAsStringAsync(ct)).Trim().Trim('"');

                // API zwraca czytelny komunikat (400/503); długie treści to błędy techniczne
                throw new RecognitionApiException(
                    body.Length is > 0 and <= 300 ? body : "Nie udało się rozpoznać rośliny. Spróbuj ponownie.");
            }
        }
    }
}
