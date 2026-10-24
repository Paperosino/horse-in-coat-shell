#include <gtk/gtk.h>
#include <stdio.h>
#ifdef ADWAITA_PROBE
#include <adwaita.h>
#endif
static GMainLoop *loop;
static gboolean capture(gpointer data) {
    GtkWidget *window = data;
    char *layout = NULL;
    g_object_get(gtk_settings_get_default(), "gtk-decoration-layout", &layout, NULL);
    printf("LAYOUT=%s\n", layout); g_free(layout);
#if GTK_MAJOR_VERSION >= 4
    GdkPaintable *paintable = gtk_widget_paintable_new(window);
    GtkSnapshot *snapshot = gtk_snapshot_new();
    int width = gtk_widget_get_width(window), height = gtk_widget_get_height(window);
    gdk_paintable_snapshot(paintable, GDK_SNAPSHOT(snapshot), width, height);
    GskRenderNode *node = gtk_snapshot_free_to_node(snapshot);
    if (!node) { g_main_loop_quit(loop); return G_SOURCE_REMOVE; }
    graphene_rect_t bounds = GRAPHENE_RECT_INIT(0,0,width,height);
    GdkTexture *texture = gsk_renderer_render_texture(gtk_native_get_renderer(GTK_NATIVE(window)), node, &bounds);
    gdk_texture_save_to_png(texture, g_getenv("GTK_PROBE_IMAGE"));
    g_object_unref(texture); gsk_render_node_unref(node); g_object_unref(paintable);
#else
    GdkWindow *surface = gtk_widget_get_window(window);
    GdkPixbuf *image = gdk_pixbuf_get_from_window(surface, 0, 0, gtk_widget_get_allocated_width(window), gtk_widget_get_allocated_height(window));
    gdk_pixbuf_save(image, g_getenv("GTK_PROBE_IMAGE"), "png", NULL, NULL); g_object_unref(image);
#endif
    fflush(stdout); g_main_loop_quit(loop); return G_SOURCE_REMOVE;
}
int main(int argc, char **argv) {
#if GTK_MAJOR_VERSION >= 4
    gtk_init();
#else
    gtk_init(&argc,&argv);
#endif
#ifdef ADWAITA_PROBE
    adw_init();
    GtkWidget *window = adw_window_new();
    GtkWidget *view = adw_toolbar_view_new();
    adw_toolbar_view_add_top_bar(ADW_TOOLBAR_VIEW(view), adw_header_bar_new());
    adw_toolbar_view_set_content(ADW_TOOLBAR_VIEW(view), gtk_label_new("Files"));
    adw_window_set_content(ADW_WINDOW(window), view);
#else
    GtkWidget *window = g_object_new(GTK_TYPE_FILE_CHOOSER_DIALOG, "use-header-bar", TRUE, "title", "Open File", "action", GTK_FILE_CHOOSER_ACTION_OPEN, NULL);
    gtk_dialog_add_button(GTK_DIALOG(window), "Cancel", GTK_RESPONSE_CANCEL);
    gtk_dialog_add_button(GTK_DIALOG(window), "Open", GTK_RESPONSE_ACCEPT);
    const char *folder=g_getenv("GTK_PROBE_FOLDER");
    if(folder) {
#if GTK_MAJOR_VERSION >= 4
        GFile *file=g_file_new_for_path(folder); gtk_file_chooser_set_current_folder(GTK_FILE_CHOOSER(window),file,NULL); g_object_unref(file);
#else
        gtk_file_chooser_set_current_folder(GTK_FILE_CHOOSER(window),folder);
#endif
    }
#endif
    gtk_window_set_default_size(GTK_WINDOW(window), 640, 480);
    loop=g_main_loop_new(NULL,FALSE);
#if GTK_MAJOR_VERSION >= 4
    gtk_window_present(GTK_WINDOW(window));
#else
    gtk_widget_show_all(window);
#endif
    g_timeout_add(900,capture,window); g_main_loop_run(loop);
#if GTK_MAJOR_VERSION >= 4
    gtk_window_destroy(GTK_WINDOW(window));
#else
    gtk_widget_destroy(window);
#endif
    g_main_loop_unref(loop); return 0;
}
