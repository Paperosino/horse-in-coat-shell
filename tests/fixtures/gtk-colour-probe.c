#include <gtk/gtk.h>
#include <stdio.h>
static void colour(GtkWidget *widget,const char *name){
#if GTK_MAJOR_VERSION == 2
 GtkStyle *style=gtk_widget_get_style(widget);
 GdkColor bg=style->bg[GTK_STATE_NORMAL],fg=style->fg[GTK_STATE_NORMAL];
 printf("%s #%02x%02x%02x #%02x%02x%02x\n",name,bg.red/257,bg.green/257,bg.blue/257,fg.red/257,fg.green/257,fg.blue/257);
#else
 GtkStyleContext *context=gtk_widget_get_style_context(widget);GdkRGBA bg,fg;
 gtk_style_context_get_background_color(context,GTK_STATE_FLAG_NORMAL,&bg);gtk_style_context_get_color(context,GTK_STATE_FLAG_NORMAL,&fg);
 printf("%s #%02x%02x%02x #%02x%02x%02x\n",name,(int)(bg.red*255+.5),(int)(bg.green*255+.5),(int)(bg.blue*255+.5),(int)(fg.red*255+.5),(int)(fg.green*255+.5),(int)(fg.blue*255+.5));
#endif
}
int main(int argc,char **argv){
 gtk_init(&argc,&argv);g_object_set(gtk_settings_get_default(),"gtk-enable-animations",FALSE,NULL);
 GtkWidget *window=gtk_window_new(GTK_WINDOW_TOPLEVEL),*button=gtk_button_new_with_label("Palette fixture");gtk_container_add(GTK_CONTAINER(window),button);
 gtk_widget_realize(window);gtk_widget_realize(button);
 while(gtk_events_pending())gtk_main_iteration();colour(window,"window");colour(button,"button");
 gtk_widget_destroy(window);return 0;
}
