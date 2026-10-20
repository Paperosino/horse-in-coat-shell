#include <wayland-client.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <stdlib.h>
#include "virtual-pointer.h"
static struct zwlr_virtual_pointer_manager_v1 *manager;
static void global(void *data,struct wl_registry *r,uint32_t name,const char *interface,uint32_t version) {
 if(!strcmp(interface,zwlr_virtual_pointer_manager_v1_interface.name))manager=wl_registry_bind(r,name,&zwlr_virtual_pointer_manager_v1_interface,1);
}
static void removed(void *data,struct wl_registry *r,uint32_t name) {}
int main(void) {
 struct wl_display *display=wl_display_connect(NULL);if(!display)return 1;
 struct wl_registry *registry=wl_display_get_registry(display);
 const struct wl_registry_listener listener={global,removed};wl_registry_add_listener(registry,&listener,NULL);wl_display_roundtrip(display);
 if(!manager)return 2;
 struct zwlr_virtual_pointer_v1 *pointer=zwlr_virtual_pointer_manager_v1_create_virtual_pointer(manager,NULL);wl_display_roundtrip(display);
 puts("ready");fflush(stdout);char line[128],op[32];unsigned x,y;
 while(fgets(line,sizeof(line),stdin)) {
  struct timespec now;clock_gettime(CLOCK_MONOTONIC,&now);uint32_t ms=now.tv_sec*1000+now.tv_nsec/1000000;
  if(sscanf(line,"%31s %u %u",op,&x,&y)!=3)break;
  if(!strcmp(op,"move"))zwlr_virtual_pointer_v1_motion_absolute(pointer,ms,x,y,getenv("HYPRSTACK_POINTER_WIDTH")?atoi(getenv("HYPRSTACK_POINTER_WIDTH")):1280,getenv("HYPRSTACK_POINTER_HEIGHT")?atoi(getenv("HYPRSTACK_POINTER_HEIGHT")):720);
  if(!strcmp(op,"button"))zwlr_virtual_pointer_v1_button(pointer,ms,x,y);
  zwlr_virtual_pointer_v1_frame(pointer);if(wl_display_roundtrip(display)<0)break;
  puts("ok");fflush(stdout);
 }
 zwlr_virtual_pointer_v1_destroy(pointer);wl_display_disconnect(display);return 0;
}
