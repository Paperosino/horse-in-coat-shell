#define _GNU_SOURCE
// Real xdg-decoration negotiation, including delayed ack and object lifetime.
#include <wayland-client.h>
#include "xdg-shell.h"
#include "xdg-decoration.h"
#include "server-decoration.h"
#include <sys/mman.h>
#include <poll.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static struct wl_display *display;
static struct wl_compositor *compositor;
static struct wl_shm *shm;
static struct xdg_wm_base *wm;
static struct zxdg_decoration_manager_v1 *manager;
static struct wl_surface *surface;
static struct xdg_surface *xdg;
static struct xdg_toplevel *top;
static struct zxdg_toplevel_decoration_v1 *deco;
static struct wl_buffer *buffer;
static struct org_kde_kwin_server_decoration_manager *legacy_manager;
static struct org_kde_kwin_server_decoration *legacy;
static int width=640,height=400,hold=0,running=1;
static uint32_t pending;
static void draw(void) {
    if(buffer)wl_buffer_destroy(buffer);
    int fd=memfd_create("hics-decoration-test",MFD_CLOEXEC);
    size_t size=(size_t)width*height*4;
    if(fd<0 || ftruncate(fd,size)<0)exit(2);
    uint32_t *pixels=mmap(NULL,size,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);
    if(pixels==MAP_FAILED)exit(2);
    for(size_t i=0;i<size/4;i++)pixels[i]=0xff264556;
    struct wl_shm_pool *pool=wl_shm_create_pool(shm,fd,size);
    buffer=wl_shm_pool_create_buffer(pool,0,width,height,width*4,WL_SHM_FORMAT_XRGB8888);
    wl_shm_pool_destroy(pool);munmap(pixels,size);close(fd);
    wl_surface_attach(surface,buffer,0,0);wl_surface_damage(surface,0,0,width,height);wl_surface_commit(surface);
}
static void configured(void *data,struct xdg_surface *s,uint32_t serial) {
    pending=serial;
    if(!hold){xdg_surface_ack_configure(s,serial);draw();}
    printf("configure %u held=%d\n",serial,hold);fflush(stdout);
}
static const struct xdg_surface_listener xdg_listener={.configure=configured};
static void resized(void *data,struct xdg_toplevel *t,int32_t w,int32_t h,struct wl_array *states) {
    if(w>0)width=w;if(h>0)height=h;
}
static void closed(void *data,struct xdg_toplevel *t){running=0;}
static const struct xdg_toplevel_listener top_listener={.configure=resized,.close=closed};
static void decorated(void *data,struct zxdg_toplevel_decoration_v1 *d,uint32_t mode){printf("decoration %u\n",mode);fflush(stdout);}
static const struct zxdg_toplevel_decoration_v1_listener deco_listener={.configure=decorated};
static void ping(void *data,struct xdg_wm_base *base,uint32_t serial){xdg_wm_base_pong(base,serial);}
static const struct xdg_wm_base_listener wm_listener={.ping=ping};
static void legacy_default(void *data,struct org_kde_kwin_server_decoration_manager *manager,uint32_t mode){}
static const struct org_kde_kwin_server_decoration_manager_listener legacy_manager_listener={.default_mode=legacy_default};
static void legacy_mode(void *data,struct org_kde_kwin_server_decoration *d,uint32_t mode){printf("legacy %u\n",mode);fflush(stdout);}
static const struct org_kde_kwin_server_decoration_listener legacy_listener={.mode=legacy_mode};
static void global(void *data,struct wl_registry *r,uint32_t id,const char *interface,uint32_t version) {
    if(!strcmp(interface,"wl_compositor"))compositor=wl_registry_bind(r,id,&wl_compositor_interface,4);
    else if(!strcmp(interface,"wl_shm"))shm=wl_registry_bind(r,id,&wl_shm_interface,1);
    else if(!strcmp(interface,"xdg_wm_base")){wm=wl_registry_bind(r,id,&xdg_wm_base_interface,1);xdg_wm_base_add_listener(wm,&wm_listener,NULL);}
    else if(!strcmp(interface,"org_kde_kwin_server_decoration_manager")){legacy_manager=wl_registry_bind(r,id,&org_kde_kwin_server_decoration_manager_interface,1);org_kde_kwin_server_decoration_manager_add_listener(legacy_manager,&legacy_manager_listener,NULL);}
    else if(!strcmp(interface,"zxdg_decoration_manager_v1"))manager=wl_registry_bind(r,id,&zxdg_decoration_manager_v1_interface,1);
}
static void removed(void *data,struct wl_registry *r,uint32_t id){}
static const struct wl_registry_listener registry_listener={.global=global,.global_remove=removed};
int main(int argc,char **argv) {
    display=wl_display_connect(NULL);if(!display)return 1;
    struct wl_registry *registry=wl_display_get_registry(display);wl_registry_add_listener(registry,&registry_listener,NULL);wl_display_roundtrip(display);
    if(!compositor||!shm||!wm||!manager)return 2;
    surface=wl_compositor_create_surface(compositor);xdg=xdg_wm_base_get_xdg_surface(wm,surface);xdg_surface_add_listener(xdg,&xdg_listener,NULL);
    top=xdg_surface_get_toplevel(xdg);xdg_toplevel_add_listener(top,&top_listener,NULL);xdg_toplevel_set_title(top,"Protocol decoration fixture");
    xdg_toplevel_set_app_id(top,argc>2?argv[2]:"org.hics.ProtocolDecoration");
    if(argc>1 && (!strncmp(argv[1],"kde-",4)||!strcmp(argv[1],"both"))){
        if(!legacy_manager)return 2;
        legacy=org_kde_kwin_server_decoration_manager_create(legacy_manager,surface);org_kde_kwin_server_decoration_add_listener(legacy,&legacy_listener,NULL);
        org_kde_kwin_server_decoration_request_mode(legacy,!strcmp(argv[1],"kde-client")?1:!strcmp(argv[1],"kde-none")?0:2);
    }
    if(argc>1 && strcmp(argv[1],"none") && strncmp(argv[1],"kde-",4)){
        deco=zxdg_decoration_manager_v1_get_toplevel_decoration(manager,top);zxdg_toplevel_decoration_v1_add_listener(deco,&deco_listener,NULL);
        if(!strcmp(argv[1],"client")||!strcmp(argv[1],"both"))zxdg_toplevel_decoration_v1_set_mode(deco,1);
        if(!strcmp(argv[1],"server"))zxdg_toplevel_decoration_v1_set_mode(deco,2);
    }
    wl_surface_commit(surface);
    while(running && wl_display_get_error(display)==0) {
        while(wl_display_prepare_read(display)!=0)wl_display_dispatch_pending(display);
        wl_display_flush(display);
        struct pollfd fds[]={{wl_display_get_fd(display),POLLIN,0},{STDIN_FILENO,POLLIN,0}};
        if(poll(fds,2,-1)<0){wl_display_cancel_read(display);break;}
        if(fds[0].revents&POLLIN)wl_display_read_events(display);else wl_display_cancel_read(display);
        wl_display_dispatch_pending(display);
        if(fds[1].revents&POLLIN){
            char command[128];if(!fgets(command,sizeof(command),stdin))break;
            if(!strncmp(command,"hold",4))hold=1;
            else if(!strncmp(command,"ack",3)){hold=0;xdg_surface_ack_configure(xdg,pending);draw();}
            else if(!strncmp(command,"legacy-server",13)&&legacy)org_kde_kwin_server_decoration_request_mode(legacy,2);
            else if(!strncmp(command,"legacy-none",11)&&legacy)org_kde_kwin_server_decoration_request_mode(legacy,0);
            else if(!strncmp(command,"client",6)&&legacy&&!deco)org_kde_kwin_server_decoration_request_mode(legacy,1);
            else if(!strncmp(command,"server",6)&&legacy&&!deco)org_kde_kwin_server_decoration_request_mode(legacy,2);
            else if(!strncmp(command,"client",6)&&deco)zxdg_toplevel_decoration_v1_set_mode(deco,1);
            else if(!strncmp(command,"server",6)&&deco)zxdg_toplevel_decoration_v1_set_mode(deco,2);
            else if(!strncmp(command,"unset",5)&&deco)zxdg_toplevel_decoration_v1_unset_mode(deco);
            else if(!strncmp(command,"destroy",7)&&deco){zxdg_toplevel_decoration_v1_destroy(deco);deco=NULL;wl_surface_commit(surface);}
            else if(!strncmp(command,"destroy",7)&&legacy){org_kde_kwin_server_decoration_release(legacy);legacy=NULL;wl_surface_commit(surface);}
            else if(!strncmp(command,"geometry",8)){xdg_surface_set_window_geometry(xdg,20,20,width-40,height-40);wl_surface_commit(surface);}
            else if(!strncmp(command,"quit",4))running=0;
            printf("command %s",command);fflush(stdout);
        }
        if(fds[1].revents&POLLHUP)break;
    }
    if(legacy)org_kde_kwin_server_decoration_release(legacy);
    if(deco)zxdg_toplevel_decoration_v1_destroy(deco);
    xdg_toplevel_destroy(top);xdg_surface_destroy(xdg);wl_surface_destroy(surface);if(buffer)wl_buffer_destroy(buffer);
    wl_display_flush(display);wl_display_disconnect(display);return 0;
}
