import pytest
from rest_framework.status import HTTP_200_OK, HTTP_403_FORBIDDEN, HTTP_400_BAD_REQUEST


class TestUserProfileViewPut:
    @pytest.mark.django_db
    def test_user_profile_view_put(self, login_client_with_user):
        client, user = login_client_with_user

        data = {
            'username': 'new_username',
            'first_name': 'new_first_name',
            'last_name': 'new_last_name',
            'email': 'new_email@mail.ru'
        }
        response = client.put(
            '/core/profile',
            data=data,
            content_type='application/json',
        )

        assert response.status_code == HTTP_200_OK, \
            f'Возвращается код {response.status_code} вместо {HTTP_200_OK}'

        user.refresh_from_db()
        assert user.username == data['username'], 'username пользователя не обновился'
        assert user.first_name == data['first_name'], 'first_name пользователя не обновился'
        assert user.last_name == data['last_name'], 'last_name пользователя не обновился'
        assert user.email == data['email'], 'email пользователя не обновился'

    @pytest.mark.django_db
    def test_user_profile_view_put_errors(self, client, user, user_with_password):
        test_user, _ = user_with_password

        # Обращение без токена
        response_1 = client.put(
            '/core/profile'
        )
        assert response_1.status_code == HTTP_403_FORBIDDEN, \
            f'Возвращается код {response_1.status_code} вместо {HTTP_403_FORBIDDEN}'

        # Обращение без данных
        client.force_login(test_user)
        response_2 = client.put(
            '/core/profile'
        )
        assert response_2.status_code == HTTP_400_BAD_REQUEST, \
            f'Возвращается код {response_2.status_code} вместо {HTTP_400_BAD_REQUEST}'

        # username и email уже используются
        data_3 = {
            'username': user.username,
            'first_name': 'new_first_name',
            'last_name': 'new_last_name',
            'email': user.email,
        }
        response_3 = client.put(
            '/core/profile',
            data=data_3,
            content_type='application/json',
        )
        assert response_3.status_code == HTTP_400_BAD_REQUEST, \
            f'Возвращается код {response_3.status_code} вместо {HTTP_400_BAD_REQUEST}'
        assert 'username' in response_3.data, 'Нет сообщения об ошибке username'
        assert 'email' in response_3.data, 'Нет сообщения об ошибке email'
