from django.urls import path

from . import api, chat, documents

urlpatterns = [
    path("register/", api.register, name="api-register"),
    path("login/", api.login, name="api-login"),
    path("me/", api.me, name="api-me"),
    path("document/", documents.document, name="api-document"),
    path("document/reindex/", documents.reindex, name="api-document-reindex"),
    path("document/search/", documents.search, name="api-document-search"),
    path("chat/", chat.state, name="api-chat"),
    path("chat/messages/", chat.send_message, name="api-chat-message"),
]
