// Minimal real X11 CSD: its header and resize grip send standard EWMH requests.
#include <xcb/xcb.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
static xcb_atom_t atom(xcb_connection_t *c, const char *name) {
    xcb_intern_atom_reply_t *r=xcb_intern_atom_reply(c,xcb_intern_atom(c,0,strlen(name),name),NULL);
    xcb_atom_t a=r?r->atom:0;free(r);return a;
}
static void request(xcb_connection_t *c,xcb_screen_t *s,xcb_window_t w,int direction,int x,int y) {
    xcb_client_message_event_t e={.response_type=XCB_CLIENT_MESSAGE,.format=32,.window=w,.type=atom(c,"_NET_WM_MOVERESIZE")};
    e.data.data32[0]=x;e.data.data32[1]=y;e.data.data32[2]=direction;e.data.data32[3]=1;e.data.data32[4]=1;
    xcb_ungrab_pointer(c,XCB_CURRENT_TIME);
    xcb_send_event(c,0,s->root,XCB_EVENT_MASK_SUBSTRUCTURE_REDIRECT|XCB_EVENT_MASK_SUBSTRUCTURE_NOTIFY,(char*)&e);xcb_flush(c);
}
int main(int argc,char **argv) {
    xcb_connection_t *c=xcb_connect(NULL,NULL);if(xcb_connection_has_error(c))return 1;
    xcb_screen_t *s=xcb_setup_roots_iterator(xcb_get_setup(c)).data;
    if(argc==4 && strcmp(argv[1],"state")==0){
        xcb_client_message_event_t e={.response_type=XCB_CLIENT_MESSAGE,.format=32,.window=strtoul(argv[2],NULL,0)};
        if(strcmp(argv[3],"minimize")==0){e.type=atom(c,"WM_CHANGE_STATE");e.data.data32[0]=3;}
        else {e.type=atom(c,"_NET_WM_STATE");e.data.data32[0]=2;e.data.data32[1]=atom(c,"_NET_WM_STATE_MAXIMIZED_HORZ");e.data.data32[2]=atom(c,"_NET_WM_STATE_MAXIMIZED_VERT");e.data.data32[3]=1;}
        xcb_send_event(c,0,s->root,XCB_EVENT_MASK_SUBSTRUCTURE_REDIRECT|XCB_EVENT_MASK_SUBSTRUCTURE_NOTIFY,(char*)&e);
        xcb_flush(c);free(xcb_get_input_focus_reply(c,xcb_get_input_focus(c),NULL));xcb_disconnect(c);return 0;
    }
    if(argc==3){request(c,s,strtoul(argv[1],NULL,0),atoi(argv[2]),0,0);free(xcb_get_input_focus_reply(c,xcb_get_input_focus(c),NULL));xcb_disconnect(c);return 0;}
    xcb_window_t w=xcb_generate_id(c);
    uint32_t values[]={0x334455,XCB_EVENT_MASK_BUTTON_PRESS|XCB_EVENT_MASK_EXPOSURE};
    xcb_create_window(c,XCB_COPY_FROM_PARENT,w,s->root,200,180,600,400,0,XCB_WINDOW_CLASS_INPUT_OUTPUT,s->root_visual,XCB_CW_BACK_PIXEL|XCB_CW_EVENT_MASK,values);
    const char klass[]="hics-csd\0org.hics.X11CsdFixture\0";
    xcb_change_property(c,XCB_PROP_MODE_REPLACE,w,XCB_ATOM_WM_CLASS,XCB_ATOM_STRING,8,sizeof(klass)-1,klass);
    const char title[]="X11 CSD drag fixture";
    xcb_change_property(c,XCB_PROP_MODE_REPLACE,w,XCB_ATOM_WM_NAME,XCB_ATOM_STRING,8,sizeof(title)-1,title);
    uint32_t pid=getpid();xcb_change_property(c,XCB_PROP_MODE_REPLACE,w,atom(c,"_NET_WM_PID"),XCB_ATOM_CARDINAL,32,1,&pid);
    uint32_t hints[]={2,0,0,0,0};xcb_change_property(c,XCB_PROP_MODE_REPLACE,w,atom(c,"_MOTIF_WM_HINTS"),atom(c,"_MOTIF_WM_HINTS"),32,5,hints);
    xcb_map_window(c,w);xcb_flush(c);printf("%u\n",w);fflush(stdout);
    xcb_generic_event_t *event;
    while((event=xcb_wait_for_event(c))) {
        if((event->response_type&127)==XCB_BUTTON_PRESS){
            xcb_button_press_event_t *b=(void*)event;
            xcb_get_geometry_reply_t *g=xcb_get_geometry_reply(c,xcb_get_geometry(c,w),NULL);
            if(b->detail==1 && g){
                if(b->event_x>=g->width-20 && b->event_y>=g->height-20)request(c,s,w,4,b->root_x,b->root_y);
                else if(b->event_y<50)request(c,s,w,8,b->root_x,b->root_y);
            }
            free(g);
        }
        free(event);
    }
    xcb_disconnect(c);return 0;
}
