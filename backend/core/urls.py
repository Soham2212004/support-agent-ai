from django.urls import path

from . import analytics, api, bot_settings, chat, documents, gdpr, public_api, publishing

urlpatterns = [
    path("register/", api.register, name="api-register"),
    path("login/", api.login, name="api-login"),
    path("me/", api.me, name="api-me"),
    path("analytics/", analytics.analytics, name="api-analytics"),
    path("analytics/export.csv", analytics.export_csv, name="api-analytics-export"),
    path("document/", documents.document, name="api-document"),
    path("document/reindex/", documents.reindex, name="api-document-reindex"),
    path("document/search/", documents.search, name="api-document-search"),
    path("chat/", chat.state, name="api-chat"),
    path("chat/messages/", chat.send_message, name="api-chat-message"),
    path("chat/messages/<int:message_id>/feedback/", chat.message_feedback, name="api-chat-message-feedback"),
    path("bot-settings/", bot_settings.bot_settings, name="api-bot-settings"),
    path("bot-settings/widget/", bot_settings.widget_mode, name="api-bot-settings-widget"),
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
    path("public/handoff/", public_api.request_handoff, name="public-handoff"),
    path("public/data-request/", gdpr.request_data_action, name="public-data-request"),
    path("public/data-request/confirm/", gdpr.confirm_data_action, name="public-data-request-confirm"),
    path(
        "public/chat/messages/<int:message_id>/feedback/",
        public_api.public_message_feedback,
        name="public-chat-feedback",
    ),
]
