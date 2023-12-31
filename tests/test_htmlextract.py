import pytest
from unittest.mock import patch

from context import profilescout
from profilescout.extraction.htmlextract import guess_name
from profilescout.extraction.ner import NamedEntityRecognition


class NERMock:
    def get_names(self, txt):
        return 


@pytest.fixture
def profile_string():
    return '''Почетна
        Факултет
            Историјат
            Деканат
            Катедре
            Службе
            Акредитација
            Обезбеђење квалитета
            Јавне набавке
            Културни живот у Ужицу
            Лепоте нашег краја
        Студије
        Основне студије
            Учитељ (240 ЕСПБ)
            Васпитач (240 ЕСПБ)
            Педагогија (240 ЕСПБ)
            Тренер у спорту (180 ЕСПБ)
        Мастер студије
            Мастер учитељ
            Мастер васпитач
        Докторске студије
        Други програми
                Програм 36 ЕСПБ
                Програм за информатику
                КП Учење и активни одмор
        Студенти
            Студентски парламент
            Стипендије и конкурси
            Студентски портал
        Наставници
            Редовни професори
            Ванредни професори
            Доценти
            Асистенти и наставници
            Извештаји о изборима у звање
            Конкурси за избор
        Наука
            Акредитација НИО
        Научни скупови
            Актуелни скупови
            Реализовани скупови
        Научни пројекти      
                Актуелни пројекти
                Реализовани пројекти
            Издаваштво
        Међународна сарадња     
            Новости
        ERASMUS+
                    Мобилност студената
                    Мобилност запослених
                Контакт/Инфо
            Прописи
            Вести
            Контакт
        проф. др Сања Маричић
        Редовни професор / By admin
        Име, средње слово, презиме: Сања М. Маричић
        Датум рођења: 29. 07. 1974. године
        Звање: Редовни професор
        Ужа научна, односно уметничка област: Методика наставе математике
        Катедра: Катедра за методике
        Кабинет: Број 35
        e-mail: sanjamaricic10@gmail.com, maricic@pfu.kg.ac.rs
        '''

class TestGuessName:
    def test_guess_name_with_origin_link_text(self, profile_string):
        ner = NamedEntityRecognition()
        with patch.object(ner, 'get_names') as mock_method:
            mock_method.return_value = ['Сања М. Маричић', 'Сања Маричић']
            result = guess_name(ner, profile_string, 'проф. др Сања Маричић')
            assert result == 'Сања Маричић'
            mock_method.assert_called_once()

    def test_guess_name_with_origin_link_text_and_invalid_names(self, profile_string):
        ner = NamedEntityRecognition()
        with patch.object(ner, 'get_names') as mock_method:
            mock_method.return_value = ['Сања М. Маричић', 'Сања Маричић', 'Петар (Пера) Петровић', 'др Петар Петровић']
            result = guess_name(ner, profile_string, 'проф. др Сања Маричић')
            assert result == 'Сања Маричић'
            mock_method.assert_called_once()

    def test_guess_name_without_origin_link_text_none(self, profile_string):
        ner = NamedEntityRecognition()
        with patch.object(ner, 'get_names') as mock_method:
            mock_method.return_value = ['Сања М. Маричић', 'Сања Маричић']
            result = guess_name(ner, profile_string, None)
            assert result == 'Сања Маричић'
            mock_method.assert_called_once()

    def test_guess_name_without_origin_link_text_none_and_invalid_names(self, profile_string):
        ner = NamedEntityRecognition()
        with patch.object(ner, 'get_names') as mock_method:
            mock_method.return_value = ['Сања М. Маричић', 'Сања Маричић', 'Петар (Пера) Петровић', 'др Петар Петровић', 'Петар Петровић']
            result = guess_name(ner, profile_string, None)
            assert result == 'Петар Петровић'
            mock_method.assert_called_once()

    def test_guess_name_without_origin_link_text_empty(self, profile_string):
        ner = NamedEntityRecognition()
        with patch.object(ner, 'get_names') as mock_method:
            mock_method.return_value = ['Сања М. Маричић', 'Сања Маричић']
            result = guess_name(ner, profile_string, '')
            assert result == 'Сања Маричић'
            mock_method.assert_called_once()
