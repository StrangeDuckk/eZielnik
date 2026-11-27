using HerbRecognition_Web.Communication.DTOs;

namespace HerbRecognition_Web.Communication.Services
{
    /// <summary>
    /// Dane przekazywane ze strony "Rozpoznaj ze zdjęcia" na kolejną stronę:
    ///   - formularz wypełniony przez model -> wyszukiwarka (/search/form?fromPhoto=1),
    ///   - zdjęcie i nazwa łacińska rośliny spoza bazy -> zgłoszenie (/plant-form?latin=…).
    /// Usługa jest "scoped", więc żyje tak długo jak połączenie użytkownika – przejście
    /// bez przeładowania strony zachowuje dane. Zdjęcie trafia na serwer dopiero
    /// wtedy, gdy użytkownik wyśle zgłoszenie.
    /// </summary>
    public class RecognitionHandoff
    {
        private PlantSearchCriteriaDTO? criteria;
        private PhotoUpload? photo;

        public void SetCriteria(PlantSearchCriteriaDTO value) => criteria = value;
        public void SetPhoto(PhotoUpload value) => photo = value;

        /// <summary>Zwraca zapisany formularz i czyści go (jednorazowo).</summary>
        public PlantSearchCriteriaDTO? TakeCriteria()
        {
            var value = criteria;
            criteria = null;
            return value;
        }

        /// <summary>Zwraca zapisane zdjęcie i czyści je (jednorazowo).</summary>
        public PhotoUpload? TakePhoto()
        {
            var value = photo;
            photo = null;
            return value;
        }
    }
}
