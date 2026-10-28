#include "eventloop.hpp"
#include "process.hpp"
#include <csignal>
#include <sdbus-c++/sdbus-c++.h>
#include <sys/eventfd.h>
#include <sys/epoll.h>
#include <unistd.h>
#include <fcntl.h>
#include <atomic>
#include <chrono>
#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <thread>
#include <vector>

using hics::portal::EventLoop;
using namespace std::chrono_literals;
static void require(bool value, const char *message) { if (!value) throw std::runtime_error(message); }
static void writeEvent(int fd) { const uint64_t value=1; require(write(fd,&value,sizeof(value))==sizeof(value),"event write"); }
static void readEvent(int fd) { uint64_t value=0; require(read(fd,&value,sizeof(value))==sizeof(value),"event read"); }
static size_t fdCount() { size_t n=0; for ([[maybe_unused]] auto &entry:std::filesystem::directory_iterator("/proc/self/fd")) ++n; return n; }
int main(int argc,char **argv) {
    try {
        require(argc==2,"mode required"); const std::string mode=argv[1];
        if(mode=="process-child"){for(;;)pause();}
        if (mode=="delete-timer" || mode=="delete-io") {
            auto loop=std::make_unique<EventLoop>(); auto *raw=loop.get();
            int fd=-1;
            if (mode=="delete-timer") loop->addTimer(0us,[&] {loop.reset();});
            else {
                fd=eventfd(0,EFD_NONBLOCK|EFD_CLOEXEC); require(fd>=0,"eventfd");
                loop->addFd(fd,EPOLLIN,[&](uint32_t) {readEvent(fd);loop.reset();});writeEvent(fd);
            }
            require(raw->run()==0 && !loop,"delete owner inside callback");
            if (fd>=0) close(fd);
        } else if (mode=="cleanup") {
            const auto baseline=fdCount();
            for (int i=0;i<100;++i) {
                EventLoop loop;
                loop.addTimer(0us,[&] {loop.exit();}); require(loop.run()==0,"cleanup loop");
            }
            require(fdCount()==baseline,"event sources/fds survive owner destruction");
            const int fd=eventfd(0,EFD_NONBLOCK|EFD_CLOEXEC);require(fd>=0,"caller fd");
            { EventLoop loop;loop.addFd(fd,EPOLLIN,[](uint32_t) {}); }
            require(fcntl(fd,F_GETFD)>=0,"loop closed caller-owned fd");close(fd);
        } else if(mode=="dbus-process-teardown") {
            EventLoop loop;hics::portal::Processes processes(loop);
            auto server=sdbus::createSessionBusConnection(sdbus::ServiceName{"org.hics.LoopProbe"});
            auto client=sdbus::createSessionBusConnection();
            server->attachSdEventLoop(loop.nativeHandle());client->attachSdEventLoop(loop.nativeHandle());
            auto object=sdbus::createObject(*server,sdbus::ObjectPath{"/org/hics/LoopProbe"});
            std::weak_ptr<sdbus::Result<>> held;bool received=false;
            object->addVTable(sdbus::registerMethod("Hold").implementedAs([&](sdbus::Result<>&& result) {
                auto reply=std::make_shared<sdbus::Result<>>(std::move(result));held=reply;
                processes.start({"/proc/self/exe","process-child"},{},2s,[reply](auto){throw std::runtime_error("Unexpected completion during shutdown");});
                received=true;loop.exit();
            })).forInterface(sdbus::InterfaceName{"org.hics.LoopProbe"});
            auto proxy=sdbus::createProxy(*client,sdbus::ServiceName{"org.hics.LoopProbe"},sdbus::ObjectPath{"/org/hics/LoopProbe"});
            const auto pending=proxy->callMethodAsync("Hold").onInterface("org.hics.LoopProbe").uponReplyInvoke([](std::optional<sdbus::Error>){});
            loop.addTimer(1s,[&]{loop.exit(2);});
            require(loop.run()==0 && received && !held.expired(),"Missing actual pending D-Bus result");
            processes.shutdown();require(held.expired(),"D-Bus result outlives connection teardown");
            object.reset();server->detachSdEventLoop();server.reset();client->detachSdEventLoop();
        } else if (mode=="dbus") {
            EventLoop loop;
            auto server=sdbus::createSessionBusConnection(sdbus::ServiceName{"org.hics.LoopProbe"});
            auto client=sdbus::createSessionBusConnection();
            server->attachSdEventLoop(loop.nativeHandle());client->attachSdEventLoop(loop.nativeHandle());
            auto object=sdbus::createObject(*server,sdbus::ObjectPath{"/org/hics/LoopProbe"});
            object->addVTable(sdbus::registerMethod("Echo").implementedAs([&](sdbus::Result<std::string> result,std::string value) {
                auto reply=std::make_shared<sdbus::Result<std::string>>(std::move(result));
                loop.addTimer(1ms,[reply,value] {reply->returnResults(value);});
            })).forInterface(sdbus::InterfaceName{"org.hics.LoopProbe"});
            auto proxy=sdbus::createProxy(*client,sdbus::ServiceName{"org.hics.LoopProbe"},sdbus::ObjectPath{"/org/hics/LoopProbe"});
            bool replied=false;
            const auto pending=proxy->callMethodAsync("Echo").onInterface("org.hics.LoopProbe").withArguments(std::string("bounded reply"))
                .uponReplyInvoke([&](std::optional<sdbus::Error> error,std::string value) {
                    require(!error && value=="bounded reply","actual async DBus reply");replied=true;loop.exit();
                });
            loop.addTimer(1s,[&] {loop.exit(2);});
            require(loop.run()==0 && replied && !pending.isPending(),"DBus dispatch failed");
        } else {
            EventLoop loop;
            loop.addTimer(2s,[&] {loop.exit(2);});
            if (mode=="timers") {
                int calls=0;
                const auto cancelled=loop.addTimer(1ms,[&] {calls+=100;});
                loop.addTimer(0us,[&] {
                    loop.removeTimer(cancelled);++calls;
                    loop.addTimer(5ms,[&] {++calls;loop.exit();});
                });
                require(loop.run()==0 && calls==2,"reentrant timer add/cancel");
            } else if (mode=="timer-storm") {
                int calls=0;
                for(int i=0;i<1000;++i) loop.addTimer(0us,[&] {
                    ++calls;loop.addTimer(0us,[&] {if(++calls==2000) loop.exit();});
                });
                require(loop.run()==0 && calls==2000,"timer mutation storm");
            } else if (mode=="throw") {
                loop.addTimer(0us,[] {throw std::runtime_error("fixture failure");});
                require(loop.run()==1,"exception crossed C callback boundary");
            } else if (mode=="thread") {
                std::atomic<bool> rejected=false;
                std::thread other([&] {try {loop.addTimer(0us,[] {});} catch(const std::logic_error &) {rejected=true;}});other.join();
                require(rejected,"cross-thread mutation accepted");loop.addTimer(0us,[&] {loop.exit();});require(loop.run()==0,"owner loop");
            } else if (mode=="hup") {
                int descriptors[2];require(pipe2(descriptors,O_CLOEXEC|O_NONBLOCK)==0,"pipe");
                int calls=0;
                loop.addFd(descriptors[0],EPOLLIN|EPOLLHUP,[&](uint32_t events) {
                    require(events&EPOLLHUP,"missing HUP");++calls;
                    loop.removeFd(descriptors[0]);close(descriptors[0]);
                    loop.addTimer(0us,[&] {loop.exit();});
                });close(descriptors[1]);require(loop.run()==0 && calls==1,"custom HUP killed loop");
            } else if (mode=="invalid") {
                bool fdRejected=false,timerRejected=false,maskRejected=false;
                try {loop.addFd(-1,EPOLLIN,[](uint32_t) {});} catch(const std::invalid_argument &) {fdRejected=true;}
                try {loop.addTimer(0us,{});} catch(const std::invalid_argument &) {timerRejected=true;}
                const int fd=eventfd(0,EFD_NONBLOCK|EFD_CLOEXEC);require(fd>=0,"eventfd");
                bool original=false;loop.addFd(fd,EPOLLIN,[&](uint32_t) {readEvent(fd);original=true;loop.exit();});
                try {loop.addFd(fd,UINT32_MAX,[](uint32_t) {});} catch(const std::system_error &) {maskRejected=true;}
                writeEvent(fd);require(loop.run()==0 && original && fdRejected && timerRejected && maskRejected,"failed replacement lost old watch");
                loop.removeFd(fd);close(fd);
            } else {
                require(mode=="fd-remove" || mode=="fd-replace" || mode=="fd-reuse","unknown mode");
                int fd=eventfd(0,EFD_NONBLOCK|EFD_CLOEXEC);require(fd>=0,"eventfd");
                int first=0,second=0;
                loop.addFd(fd,EPOLLIN,[&](uint32_t) {
                    readEvent(fd);++first;
                    if(mode=="fd-remove") {loop.removeFd(fd);loop.addTimer(0us,[&] {loop.exit();});return;}
                    if(mode=="fd-reuse") {
                        const int old=fd;loop.removeFd(fd);close(fd);fd=eventfd(0,EFD_NONBLOCK|EFD_CLOEXEC);require(fd==old,"fd number reuse fixture");
                    }
                    loop.addFd(fd,EPOLLIN,[&](uint32_t) {readEvent(fd);++second;loop.removeFd(fd);loop.exit();});writeEvent(fd);
                });writeEvent(fd);
                require(loop.run()==0 && first==1 && second==(mode=="fd-remove"?0:1),"fd self mutation");
                loop.removeFd(fd);close(fd);
            }
        }
        std::cout<<"PASS "<<mode<<'\n';return 0;
    } catch(const std::exception &error) {std::cerr<<"FAIL: "<<error.what()<<'\n';return 1;}
}
