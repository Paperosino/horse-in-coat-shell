#include <gtk/gtk.h>
#ifdef ADWAITA_PROBE
#include <adwaita.h>
#endif
static GMainLoop *loop;
static gboolean capture(gpointer data) {
 GtkWidget *window=data;
 GdkPaintable *paintable=gtk_widget_paintable_new(window);
 GtkSnapshot *snapshot=gtk_snapshot_new();
 int width=gtk_widget_get_width(window),height=gtk_widget_get_height(window);
 gdk_paintable_snapshot(paintable,GDK_SNAPSHOT(snapshot),width,height);
 GskRenderNode *node=gtk_snapshot_free_to_node(snapshot);
 if(!node){g_printerr("No rendered GTK4 content\n");g_main_loop_quit(loop);return G_SOURCE_REMOVE;}
 graphene_rect_t bounds=GRAPHENE_RECT_INIT(0,0,width,height);
 GdkTexture *texture=gsk_renderer_render_texture(gtk_native_get_renderer(GTK_NATIVE(window)),node,&bounds);
 gdk_texture_save_to_png(texture,g_getenv("GTK_PROBE_IMAGE"));
 g_object_unref(texture);gsk_render_node_unref(node);g_object_unref(paintable);
 g_main_loop_quit(loop);return G_SOURCE_REMOVE;
}
int main(void){
 gtk_init();
#ifdef ADWAITA_PROBE
 adw_init();
#endif
 g_object_set(gtk_settings_get_default(),"gtk-enable-animations",FALSE,NULL);
 GtkWidget *box=gtk_box_new(GTK_ORIENTATION_VERTICAL,12);
#ifdef ADWAITA_PROBE
 GtkWidget *window=adw_window_new();adw_window_set_content(ADW_WINDOW(window),box);
#else
 GtkWidget *window=gtk_window_new();gtk_window_set_child(GTK_WINDOW(window),box);
#endif
 gtk_window_set_default_size(GTK_WINDOW(window),400,400);
 gtk_widget_set_margin_start(box,24);gtk_widget_set_margin_end(box,24);gtk_widget_set_margin_top(box,24);
 const char *classes[]={"normal","suggested-action","destructive-action","flat"};
 for(int i=0;i<4;i++){GtkWidget *button=gtk_button_new_with_label(classes[i]);gtk_widget_add_css_class(button,classes[i]);gtk_widget_set_size_request(button,-1,54);gtk_box_append(GTK_BOX(box),button);}
 gtk_box_append(GTK_BOX(box),gtk_entry_new());
 loop=g_main_loop_new(NULL,FALSE);gtk_window_present(GTK_WINDOW(window));g_timeout_add(700,capture,window);g_main_loop_run(loop);
 gtk_window_destroy(GTK_WINDOW(window));g_main_loop_unref(loop);return 0;
}
