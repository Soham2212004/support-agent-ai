from django.urls import path

from . import api, bot_settings, chat, documents, public_api, publishing

urlpatterns = [
    path("register/", api.register, name="api-register"),
    path("login/", api.login, name="api-login"),
    path("me/", api.me, name="api-me"),
    path("document/", documents.document, name="api-document"),
    path("document/reindex/", documents.reindex, name="api-document-reindex"),
    path("document/search/", documents.search, name="api-document-search"),
    path("chat/", chat.state, name="api-chat"),
    path("chat/messages/", chat.send_message, name="api-chat-message"),
    path("bot-settings/", bot_settings.bot_settings, name="api-bot-settings"),
    path("publication/", publishing.publication, name="api-publication"),
    path("publication/publish/", publishing.publish, name="api-publish"),
    path("publication/unpublish/", publishing.unpublish, name="api-unpublish"),
    path(
        "publication/versions/<int:version_id>/restore/",
        publishing.restore_version,
        name="api-restore-version",
    ),
    path("publication/api-key/", publishing.api_keys, name="api-client-key"),
    path("publication/websites/", publishing.allowed_websites, name="api-allowed-websites"),
    path("public/token/", public_api.visitor_token, name="public-visitor-token"),
    path("public/chat/", public_api.public_chat, name="public-chat"),
]
