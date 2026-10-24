#pragma once
#include <hyprland/src/managers/screenshare/ScreenshareManager.hpp>

// Pinned ABI adapter. Explicit member-pointer instantiation is permitted to
// name private members (C++23 [temp.spec.general]/6); it does not change upstream class
// definitions or rewrite access specifiers in transitive standard headers.
namespace hics::capture {
namespace { // TU-local tags keep one explicit instantiation per specialization (C++23 [temp.spec.general]/5-6).
template<class Tag, typename Tag::Type Member> struct Access {
    friend typename Tag::Type member(Tag) { return Member; }
};
#define HICS_CAPTURE_MEMBER(Name, Class, Field, ...) \
    struct Name { using Type = __VA_ARGS__ Class::*; friend Type member(Name); }; \
    template struct Access<Name, &Class::Field>;
HICS_CAPTURE_MEMBER(Pending, Screenshare::CScreenshareManager, m_pendingFrames, std::vector<WP<Screenshare::CScreenshareFrame>>)
HICS_CAPTURE_MEMBER(Shared, Screenshare::CScreenshareFrame, m_shared, bool)
HICS_CAPTURE_MEMBER(Copying, Screenshare::CScreenshareFrame, m_copyInFlight, bool)
HICS_CAPTURE_MEMBER(Session, Screenshare::CScreenshareFrame, m_session, WP<Screenshare::CScreenshareSession>)
HICS_CAPTURE_MEMBER(Kind, Screenshare::CScreenshareSession, m_type, Screenshare::eScreenshareType)
HICS_CAPTURE_MEMBER(Window, Screenshare::CScreenshareSession, m_window, PHLWINDOWREF)
#undef HICS_CAPTURE_MEMBER
struct Copy { using Type = void (Screenshare::CScreenshareFrame::*)(); friend Type member(Copy); };
template struct Access<Copy, &Screenshare::CScreenshareFrame::copy>;
}
} // namespace hics::capture
