using HerbRecognition_APIs.Services;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.RateLimiting;

namespace HerbRecognition_APIs.Controllers
{
    [ApiController]
    [Route("api/recognize")]
    [EnableRateLimiting("recognize")]
    public class RecognitionController(IRecognitionService recognition) : ControllerBase
    {
        // Kestrel ma globalnie 1 MB – tu podnosimy limit tylko dla zdjęcia.
        // Strona zmniejsza zdjęcie do 1024 px, więc zwykle to ok. 100–300 KB.
        private const long MaxUploadBytes = 10 * 1024 * 1024;

        // POST api/recognize  (multipart/form-data, pole "photo")
        [HttpPost]
        [RequestSizeLimit(MaxUploadBytes)]
        [RequestFormLimits(MultipartBodyLengthLimit = MaxUploadBytes)]
        public async Task<IActionResult> Recognize(IFormFile? photo, CancellationToken ct)
        {
            if (photo is null || photo.Length == 0)
                return BadRequest("Dodaj zdjęcie rośliny.");

            if (photo.Length > MaxUploadBytes)
                return BadRequest("Zdjęcie jest za duże (maksymalnie 10 MB).");

            if (!photo.ContentType.StartsWith("image/", StringComparison.OrdinalIgnoreCase))
                return BadRequest("Wybrany plik nie jest zdjęciem.");

            byte[] image;
            await using (var stream = photo.OpenReadStream())
            using (var buffer = new MemoryStream())
            {
                await stream.CopyToAsync(buffer, ct);
                image = buffer.ToArray();
            }

            try
            {
                return Ok(await recognition.RecognizeAsync(image, ct));
            }
            catch (RecognitionUnavailableException ex)
            {
                return StatusCode(StatusCodes.Status503ServiceUnavailable, ex.Message);
            }
            catch (ArgumentException ex)
            {
                return BadRequest(ex.Message);
            }
        }
    }
}
