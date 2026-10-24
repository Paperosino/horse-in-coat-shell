#pragma once
#include <hyprland/src/managers/input/InputManager.hpp>
#include <hyprland/src/managers/KeybindManager.hpp>
#include <hyprland/src/render/OpenGL.hpp>
#include <hyprland/src/render/Renderer.hpp>
#include <hyprland/src/render/pass/Pass.hpp>
#include <hyprland/src/render/decorations/CHyprGroupBarDecoration.hpp>
#include <hyprland/src/render/decorations/DecorationPositioner.hpp>
#include <hyprland/src/desktop/state/FocusState.hpp>
#include <hyprland/src/desktop/view/Group.hpp>
#include <hyprland/src/desktop/view/Popup.hpp>
#include <hyprland/src/desktop/view/Window.hpp>
#include <hyprland/src/layout/algorithm/tiled/scrolling/ScrollingAlgorithm.hpp>
#include <memory>
#include <utility>

// Pinned ABI adapters. Explicit instantiation may name private members without
// changing class definitions or access specifiers in transitive headers.
namespace HicsPinned {
template<class Tag, auto Pointer> struct Access { friend auto member(Tag) { return Pointer; } };
#define HICS_PINNED_MEMBER(Tag, Class, Name) \
    struct Tag { friend auto member(Tag); }; \
    template struct Access<Tag, &Class::Name>;
HICS_PINNED_MEMBER(CursorSurface, CInputManager, m_cursorSurfaceInfo)
HICS_PINNED_MEMBER(FinalShader, Render::GL::CHyprOpenGLImpl, m_finalScreenShader)
HICS_PINNED_MEMBER(ScrollingData, Layout::Tiled::CScrollingAlgorithm, m_scrollingData)
HICS_PINNED_MEMBER(ScrollingFocus, Layout::Tiled::CScrollingAlgorithm, focusTargetUpdate)
HICS_PINNED_MEMBER(PopupResource, Desktop::View::CPopup, m_resource)
HICS_PINNED_MEMBER(PopupOwner, Desktop::View::CPopup, m_windowOwner)
HICS_PINNED_MEMBER(PopupParentCoords, Desktop::View::CPopup, t1ParentCoords)
HICS_PINNED_MEMBER(FocusWindow, Desktop::CFocusState, m_focusWindow)
HICS_PINNED_MEMBER(FocusSurface, Desktop::CFocusState, m_focusSurface)
HICS_PINNED_MEMBER(PassElements, Render::CRenderPass, m_passElements)
HICS_PINNED_MEMBER(DecorationData, CDecorationPositioner, getDataFor)
HICS_PINNED_MEMBER(GroupBarBox, CHyprGroupBarDecoration, m_assignedBox)
HICS_PINNED_MEMBER(GroupVisibility, Desktop::View::CGroup, updateWindowVisibility)
HICS_PINNED_MEMBER(WindowHidden, Desktop::View::CWindow, m_hidden)
HICS_PINNED_MEMBER(ScrollTimer, CKeybindManager, m_scrollTimer)
HICS_PINNED_MEMBER(RenderWindow, Render::IHyprRenderer, renderWindow)
HICS_PINNED_MEMBER(RenderLayer, Render::IHyprRenderer, renderLayer)
HICS_PINNED_MEMBER(RenderBackground, Render::IHyprRenderer, renderBackground)
#undef HICS_PINNED_MEMBER
struct ShouldBlur { friend auto member(ShouldBlur); };
template struct Access<ShouldBlur, static_cast<bool (Render::IHyprRenderer::*)(PHLWINDOW)>(&Render::IHyprRenderer::shouldBlur)>;

template<class Object, class Tag> decltype(auto) field(const Object& object, Tag tag) {
    return (std::to_address(object)->*member(tag));
}
template<class Object, class Tag, class... Args> decltype(auto) call(const Object& object, Tag tag, Args&&... args) {
    return (std::to_address(object)->*member(tag))(std::forward<Args>(args)...);
}
}
