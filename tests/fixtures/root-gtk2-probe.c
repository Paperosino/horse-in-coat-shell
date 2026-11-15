#include <gtk/gtk.h>
int main(int argc, char **argv) {
    gtk_init(&argc, &argv);
    GtkWidget *window = gtk_window_new(GTK_WINDOW_TOPLEVEL);
    gtk_widget_realize(window);
    const GdkColor colour = gtk_widget_get_style(window)->bg[GTK_STATE_NORMAL];
    g_print("#%02x%02x%02x\n", colour.red / 257, colour.green / 257, colour.blue / 257);
    gtk_widget_destroy(window);
    return 0;
}
