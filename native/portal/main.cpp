// A separate, ephemeral WebKit process: no browser profile or shell JS context.
#include <clocale>
#include <cstring>
#include <gtk/gtk.h>
#include <libintl.h>
#include <webkit/webkit.h>
static const char *target;
static bool http(const char *uri) {
  return uri && (g_str_has_prefix(uri, "http://") ||
                 g_str_has_prefix(uri, "https://"));
}
static gboolean permission(WebKitWebView *, WebKitPermissionRequest *request,
                           gpointer) {
  webkit_permission_request_deny(request);
  return TRUE;
}
static gboolean policy(WebKitWebView *, WebKitPolicyDecision *decision,
                       WebKitPolicyDecisionType type, gpointer) {
  if (type == WEBKIT_POLICY_DECISION_TYPE_NAVIGATION_ACTION ||
      type == WEBKIT_POLICY_DECISION_TYPE_NEW_WINDOW_ACTION) {
    auto *action = webkit_navigation_policy_decision_get_navigation_action(
        WEBKIT_NAVIGATION_POLICY_DECISION(decision));
    const char *uri = webkit_uri_request_get_uri(
        webkit_navigation_action_get_request(action));
    if (!http(uri)) {
      webkit_policy_decision_ignore(decision);
      return TRUE;
    }
  }
  return FALSE;
}
static void showBrowser(GtkApplication *app, WebKitWebView *view,
                        const char *initial) {
  auto *window = gtk_application_window_new(app);
  gtk_window_set_title(GTK_WINDOW(window), gettext("Network sign-in"));
  gtk_window_set_default_size(GTK_WINDOW(window), 620, 760);
  auto *box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 8);
  auto *header = gtk_header_bar_new();
  gtk_window_set_titlebar(GTK_WINDOW(window), header);
  auto *retry = gtk_button_new_from_icon_name("view-refresh-symbolic");
  gtk_widget_set_tooltip_text(retry, gettext("Reload"));
  gtk_header_bar_pack_end(GTK_HEADER_BAR(header), retry);
  g_signal_connect_swapped(retry, "clicked", G_CALLBACK(webkit_web_view_reload),
                           view);
  auto *label =
      gtk_label_new(gettext("Network sign-in · Temporary browser session"));
  gtk_widget_set_margin_top(label, 8);
  gtk_widget_set_margin_bottom(label, 8);
  gtk_box_append(GTK_BOX(box), label);
  auto *location = gtk_label_new(initial);
  gtk_label_set_ellipsize(GTK_LABEL(location), PANGO_ELLIPSIZE_MIDDLE);
  gtk_label_set_selectable(GTK_LABEL(location), TRUE);
  gtk_box_append(GTK_BOX(box), location);
  g_signal_connect(
      view, "notify::uri",
      G_CALLBACK(+[](GObject *object, GParamSpec *, gpointer data) {
        const auto *uri = webkit_web_view_get_uri(WEBKIT_WEB_VIEW(object));
        gtk_label_set_text(GTK_LABEL(data), uri ? uri : "");
      }),
      location);
  g_signal_connect(view, "permission-request", G_CALLBACK(permission), nullptr);
  g_signal_connect(view, "decide-policy", G_CALLBACK(policy), nullptr);
  g_signal_connect(
      view, "load-failed",
      G_CALLBACK(+[](WebKitWebView *, WebKitLoadEvent, const gchar *,
                     GError *error, gpointer data) -> gboolean {
        gtk_label_set_text(GTK_LABEL(data), error->message);
        return FALSE;
      }),
      label);
  g_signal_connect_swapped(view, "close", G_CALLBACK(gtk_window_destroy),
                           window);
  g_signal_connect(
      view, "create",
      G_CALLBACK(+[](WebKitWebView *source, WebKitNavigationAction *action,
                     gpointer data) -> WebKitWebView * {
        const auto *uri = webkit_uri_request_get_uri(
            webkit_navigation_action_get_request(action));
        if (!http(uri) || !webkit_navigation_action_is_user_gesture(action) ||
            g_list_length(gtk_application_get_windows(GTK_APPLICATION(data))) >=
                4)
          return nullptr;
        auto *child = WEBKIT_WEB_VIEW(g_object_new(
            WEBKIT_TYPE_WEB_VIEW, "related-view", source, nullptr));
        showBrowser(GTK_APPLICATION(data), child, uri);
        return child;
      }),
      app);
  gtk_widget_set_vexpand(GTK_WIDGET(view), TRUE);
  gtk_box_append(GTK_BOX(box), GTK_WIDGET(view));
  gtk_window_set_child(GTK_WINDOW(window), box);
  gtk_window_present(GTK_WINDOW(window));
}
static void activate(GtkApplication *app, gpointer) {
  auto *session = webkit_network_session_new_ephemeral();
  auto *view = WEBKIT_WEB_VIEW(
      g_object_new(WEBKIT_TYPE_WEB_VIEW, "network-session", session, nullptr));
  g_signal_connect(
      session, "download-started",
      G_CALLBACK(+[](WebKitNetworkSession *, WebKitDownload *download,
                     gpointer) { webkit_download_cancel(download); }),
      nullptr);
  showBrowser(app, view, target);
  webkit_web_view_load_uri(view, target);
  g_object_unref(session);
}
int main(int argc, char **argv) {
  if (argc != 2 || !http(argv[1]) || std::strlen(argv[1]) > 4096)
    return 2;
  setlocale(LC_ALL, "");
  bindtextdomain("hyprstack", HICS_LOCALE_DIR);
  bind_textdomain_codeset("hyprstack", "UTF-8");
  textdomain("hyprstack");
  target = argv[1];
  auto *app =
      gtk_application_new("org.hics.CaptivePortal", G_APPLICATION_NON_UNIQUE);
  g_signal_connect(app, "activate", G_CALLBACK(activate), nullptr);
  int result = g_application_run(G_APPLICATION(app), 1, argv);
  g_object_unref(app);
  return result;
}
