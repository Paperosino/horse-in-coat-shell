#define _GNU_SOURCE
#include <wayland-client.h>
#include <xkbcommon/xkbcommon.h>
#include <sys/mman.h>
#include <unistd.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include "virtual-keyboard.h"
static struct wl_seat *seat;
static struct zwp_virtual_keyboard_manager_v1 *manager;
static void global(void *data,struct wl_registry *registry,uint32_t name,const char *interface,uint32_t version){
 (void)data;(void)version;
 if(!strcmp(interface,"wl_seat"))seat=wl_registry_bind(registry,name,&wl_seat_interface,1);
 if(!strcmp(interface,"zwp_virtual_keyboard_manager_v1"))manager=wl_registry_bind(registry,name,&zwp_virtual_keyboard_manager_v1_interface,1);
}
static void removed(void *data,struct wl_registry *registry,uint32_t name){(void)data;(void)registry;(void)name;}
int main(int argc,char **argv){
 if(argc!=2)return 2;
 struct wl_display *display=wl_display_connect(NULL);if(!display)return 3;
 struct wl_registry *registry=wl_display_get_registry(display);
 const struct wl_registry_listener listener={global,removed};wl_registry_add_listener(registry,&listener,NULL);wl_display_roundtrip(display);
 if(!seat||!manager)return 4;
 struct xkb_context *context=xkb_context_new(XKB_CONTEXT_NO_FLAGS);
 struct xkb_rule_names names={.layout="us"};struct xkb_keymap *map=xkb_keymap_new_from_names(context,&names,XKB_KEYMAP_COMPILE_NO_FLAGS);
 char *text=xkb_keymap_get_as_string(map,XKB_KEYMAP_FORMAT_TEXT_V1);size_t size=strlen(text)+1;
 int fd=memfd_create("hics-test-keyboard",MFD_CLOEXEC);if(fd<0)return 5;
 if(write(fd,text,size)!=(ssize_t)size)return 6;
 struct zwp_virtual_keyboard_v1 *keyboard=zwp_virtual_keyboard_manager_v1_create_virtual_keyboard(manager,seat);
 zwp_virtual_keyboard_v1_keymap(keyboard,1,fd,(uint32_t)size);wl_display_roundtrip(display);
 zwp_virtual_keyboard_v1_modifiers(keyboard,1u<<xkb_keymap_mod_get_index(map,XKB_MOD_NAME_LOGO),0,0,0);
 zwp_virtual_keyboard_v1_key(keyboard,1,(uint32_t)atoi(argv[1]),1);wl_display_roundtrip(display);usleep(30000);
 zwp_virtual_keyboard_v1_key(keyboard,40,(uint32_t)atoi(argv[1]),0);zwp_virtual_keyboard_v1_modifiers(keyboard,0,0,0,0);wl_display_roundtrip(display);
 zwp_virtual_keyboard_v1_destroy(keyboard);wl_display_roundtrip(display);close(fd);free(text);xkb_keymap_unref(map);xkb_context_unref(context);wl_display_disconnect(display);return 0;
}
