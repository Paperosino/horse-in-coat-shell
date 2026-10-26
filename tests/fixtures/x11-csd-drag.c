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
    if(argc==4 && strcmp(argv[1],"motif")==0){
        xcb_window_t id=strtoul(argv[2],NULL,0);xcb_atom_t prop=atom(c,"_MOTIF_WM_HINTS");
        if(!strcmp(argv[3],"delete"))xcb_delete_property(c,id,prop);
        else if(!strcmp(argv[3],"invalid")){const char bad[]="x";xcb_change_property(c,XCB_PROP_MODE_REPLACE,id,prop,XCB_ATOM_STRING,8,1,bad);}
        else {uint32_t hints[]={!strcmp(argv[3],"functions")?1:2,0,strtoul(argv[3],NULL,0),0,0};xcb_change_property(c,XCB_PROP_MODE_REPLACE,id,prop,prop,32,5,hints);}
        xcb_flush(c);free(xcb_get_input_focus_reply(c,xcb_get_input_focus(c),NULL));xcb_disconnect(c);return 0;
    }
    if(argc==4 && strcmp(argv[1],"state")==0){
        xcb_client_message_event_t e={.response_type=XCB_CLIENT_MESSAGE,.format=32,.window=strtoul(argv[2],NULL,0)};
        if(strcmp(argv[3],"minimize")==0){e.type=atom(c,"WM_CHANGE_STATE");e.data.data32[0]=3;}
        else {e.type=atom(c,"_NET_WM_STATE");e.data.data32[0]=2;e.data.data32[1]=atom(c,"_NET_WM_STATE_MAXIMIZED_HORZ");e.data.data32[2]=atom(c,"_NET_WM_STATE_MAXIMIZED_VERT");e.data.data32[3]=1;}
        xcb_send_event(c,0,s->root,XCB_EVENT_MASK_SUBSTRUCTURE_REDIRECT|XCB_EVENT_MASK_SUBSTRUCTURE_NOTIFY,(char*)&e);
        xcb_flush(c);free(xcb_get_input_focus_reply(c,xcb_get_input_focus(c),NULL));xcb_disconnect(c);return 0;
    }
    if(argc==3){request(c,s,strtoul(argv[1],NULL,0),atoi(argv[2]),0,0);free(xcb_get_input_focus_reply(c,xcb_get_input_focus(c),NULL));xcb_disconnect(c);return 0;}
    xcb_window_t w=xcb_generate_id(c);
    uint32_t values[]={0x334455,XCB_EVENT_MASK_BUTTON_PRESS|XCB_EVENT_MASK_EXPOSURE|XCB_EVENT_MASK_KEY_PRESS|XCB_EVENT_MASK_FOCUS_CHANGE};
    xcb_create_window(c,XCB_COPY_FROM_PARENT,w,s->root,200,180,600,400,0,XCB_WINDOW_CLASS_INPUT_OUTPUT,s->root_visual,XCB_CW_BACK_PIXEL|XCB_CW_EVENT_MASK,values);
    const char klass[]="hics-csd\0org.hics.X11CsdFixture\0";
    xcb_change_property(c,XCB_PROP_MODE_REPLACE,w,XCB_ATOM_WM_CLASS,XCB_ATOM_STRING,8,sizeof(klass)-1,klass);
    const char title[]="X11 CSD drag fixture";
    xcb_change_property(c,XCB_PROP_MODE_REPLACE,w,XCB_ATOM_WM_NAME,XCB_ATOM_STRING,8,sizeof(title)-1,title);
    uint32_t pid=getpid();xcb_change_property(c,XCB_PROP_MODE_REPLACE,w,atom(c,"_NET_WM_PID"),XCB_ATOM_CARDINAL,32,1,&pid);
    if(getenv("HICS_TEST_GLOBALLY_ACTIVE")){
        uint32_t hints[]={1,0,0,0,0,0,0,0,0};
        xcb_change_property(c,XCB_PROP_MODE_REPLACE,w,XCB_ATOM_WM_HINTS,XCB_ATOM_WM_HINTS,32,9,hints);
        xcb_atom_t take=atom(c,"WM_TAKE_FOCUS");xcb_change_property(c,XCB_PROP_MODE_REPLACE,w,atom(c,"WM_PROTOCOLS"),XCB_ATOM_ATOM,32,1,&take);
    }
    const char *initial=getenv("HICS_TEST_MOTIF");
    uint32_t hints[]={2,0,initial?strtoul(initial,NULL,0):0,0,0};
    if(!initial || strcmp(initial,"none"))xcb_change_property(c,XCB_PROP_MODE_REPLACE,w,atom(c,"_MOTIF_WM_HINTS"),atom(c,"_MOTIF_WM_HINTS"),32,5,hints);
    if(!getenv("HICS_TEST_NO_MAP"))xcb_map_window(c,w);xcb_flush(c);printf("%u\n",w);fflush(stdout);
    const char *key_log=getenv("HICS_TEST_KEY_LOG");
    xcb_generic_event_t *event;
    while((event=xcb_wait_for_event(c))) {
        if((event->response_type&127)==XCB_CLIENT_MESSAGE){
            xcb_client_message_event_t *message=(void*)event;
            if(message->type==atom(c,"WM_PROTOCOLS") && message->data.data32[0]==atom(c,"WM_TAKE_FOCUS")){
                xcb_set_input_focus(c,XCB_INPUT_FOCUS_POINTER_ROOT,w,message->data.data32[1]);xcb_flush(c);
            }
        }
        if((event->response_type&127)==XCB_KEY_PRESS && key_log){
            FILE *log=fopen(key_log,"a");if(log){fprintf(log,"%u\n",((xcb_key_press_event_t*)event)->detail);fclose(log);}
        }
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
