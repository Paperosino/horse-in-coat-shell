#include <adwaita.h>

static GMainLoop *loop;
static GtkWidget *window;
static AdwDialog *dialog;
static int phase;

static void paint(GtkDrawingArea *area, cairo_t *cr, int w, int h, gpointer data) {
    cairo_set_source_rgb(cr, .1, .8, .2);
    cairo_paint(cr);
    cairo_set_source_rgb(cr, .8, .1, .2);
    cairo_rectangle(cr, w / 2, 0, w / 2, h);
    cairo_fill(cr);
}

static gboolean capture(gpointer data) {
    GdkPaintable *paintable = gtk_widget_paintable_new(window);
    GtkSnapshot *snapshot = gtk_snapshot_new();
    int w = gtk_widget_get_width(window), h = gtk_widget_get_height(window);
    gdk_paintable_snapshot(paintable, GDK_SNAPSHOT(snapshot), w, h);
    GskRenderNode *node = gtk_snapshot_free_to_node(snapshot);
    if (!node) g_error("No rendered dialog content");
    graphene_rect_t bounds = GRAPHENE_RECT_INIT(0, 0, w, h);
    GdkTexture *texture = gsk_renderer_render_texture(gtk_native_get_renderer(GTK_NATIVE(window)), node, &bounds);
    char *path = g_strdup_printf("%s-%d.png", g_getenv("GTK_PROBE_IMAGE"), phase);
    if (!gdk_texture_save_to_png(texture, path)) g_error("Cannot save dialog capture");
    g_free(path); g_object_unref(texture); gsk_render_node_unref(node); g_object_unref(paintable);
    if (phase == 0) adw_dialog_present(dialog, window);
    else if (phase == 1) adw_dialog_force_close(dialog);
    else { g_main_loop_quit(loop); return G_SOURCE_REMOVE; }
    phase++;
    return G_SOURCE_CONTINUE;
}

int main(int argc, char **argv) {
    adw_init();
    g_object_set(gtk_settings_get_default(), "gtk-enable-animations", FALSE, NULL);
    window = adw_window_new();
    GtkWidget *content = gtk_drawing_area_new();
    gtk_drawing_area_set_draw_func(GTK_DRAWING_AREA(content), paint, NULL, NULL);
    adw_window_set_content(ADW_WINDOW(window), content);
    gtk_window_set_default_size(GTK_WINDOW(window), 800, 600);
    dialog = adw_dialog_new();
    g_object_ref_sink(dialog);
    adw_dialog_set_content_width(dialog, 300);
    adw_dialog_set_content_height(dialog, 200);
    adw_dialog_set_presentation_mode(dialog, argc > 1 ? ADW_DIALOG_BOTTOM_SHEET : ADW_DIALOG_FLOATING);
    adw_dialog_set_child(dialog, gtk_label_new("Modal dialog"));
    loop = g_main_loop_new(NULL, FALSE);
    gtk_window_present(GTK_WINDOW(window));
    g_timeout_add(500, capture, NULL);
    g_main_loop_run(loop);
    g_object_unref(dialog); gtk_window_destroy(GTK_WINDOW(window)); g_main_loop_unref(loop);
    return 0;
}
