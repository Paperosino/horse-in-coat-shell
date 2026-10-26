#include "barDeco.hpp"
#include <hyprland/src/desktop/state/ViewState.hpp>
#include <hyprland/src/managers/SessionLockManager.hpp>

#include <hyprland/src/Compositor.hpp>
#include <hyprland/src/desktop/state/FocusState.hpp>
#include <hyprland/src/desktop/state/WindowState.hpp>
#include <hyprland/src/desktop/state/LayerState.hpp>
#include <hyprland/src/desktop/state/ViewHitTester.hpp>
#include <hyprland/src/desktop/view/Window.hpp>
#include <hyprland/src/desktop/view/LayerSurface.hpp>
#include <hyprland/src/helpers/MiscFunctions.hpp>
#include <hyprland/src/managers/SeatManager.hpp>
#include <hyprland/src/managers/input/InputManager.hpp>
#include <hyprland/src/render/Renderer.hpp>
#include <hyprland/src/config/ConfigManager.hpp>
#include <hyprland/src/protocols/XDGShell.hpp>
#include <hyprland/src/xwayland/XSurface.hpp>
#include <hyprland/src/config/shared/animation/AnimationTree.hpp>
#include <hyprland/src/config/shared/parserUtils/ParserUtils.hpp>
#include <hyprland/src/config/supplementary/executor/Executor.hpp>
#include <hyprland/src/config/shared/actions/ConfigActions.hpp>
#include <hyprland/src/animation/AnimationManager.hpp>
#include <hyprland/src/protocols/LayerShell.hpp>
#include <hyprland/src/event/EventBus.hpp>
#include <hyprland/src/layout/LayoutManager.hpp>
#include <hyprland/src/render/OpenGL.hpp>
#include <hyprland/src/state/MonitorState.hpp>

#include "globals.hpp"
#include "BarPassElement.hpp"

#include <climits>
#include <pango/pangocairo.h>
#include "titlebar-controls.hpp"
#include "titlebar-actions.hpp"
#include <hyprland/src/managers/fullscreen/FullscreenController.hpp>

using namespace Render::GL;

// Render synchronously inside the decoration pass; the asynchronous resource
// gatherer cannot be awaited safely while that pass owns the renderer context.
static SP<Render::ITexture> renderDecorationText(const std::string& text, const CHyprColor& color,
    int size, const std::string& font, int maxWidth, int weight = 400) {
    auto options = cairo_font_options_create();
    cairo_font_options_set_antialias(options, CAIRO_ANTIALIAS_GRAY);
    cairo_font_options_set_hint_style(options, CAIRO_HINT_STYLE_FULL);
    cairo_font_options_set_hint_metrics(options, CAIRO_HINT_METRICS_ON);
    auto context = pango_font_map_create_context(pango_cairo_font_map_get_default());
    pango_cairo_context_set_font_options(context, options);
    auto layout = pango_layout_new(context);
    g_object_unref(context);
    auto description = pango_font_description_new();
    pango_font_description_set_family(description, font.c_str());
    pango_font_description_set_absolute_size(description, size * PANGO_SCALE);
    pango_font_description_set_weight(description, static_cast<PangoWeight>(weight));
    pango_layout_set_font_description(layout, description);
    pango_layout_set_text(layout, text.c_str(), -1);
    pango_layout_set_single_paragraph_mode(layout, true);
    if (maxWidth > 0) {
        pango_layout_set_width(layout, maxWidth * PANGO_SCALE);
        pango_layout_set_ellipsize(layout, PANGO_ELLIPSIZE_END);
    }
    PangoRectangle ink{}, logical{};
    pango_layout_get_pixel_extents(layout, &ink, &logical);
    const int width = std::max(1, std::max(logical.width, ink.x + ink.width));
    const int height = std::max(1, std::max(logical.height, ink.y + ink.height));
    auto surface = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, width, height);
    auto cairo = cairo_create(surface);
    cairo_set_font_options(cairo, options);
    cairo_set_source_rgba(cairo, color.r, color.g, color.b, color.a);
    pango_cairo_show_layout(cairo, layout);
    cairo_surface_flush(surface);
    auto texture = g_pHyprRenderer->createTexture(surface);
    texture->m_imageDescription = NColorManagement::getDefaultImageDescription();
    cairo_destroy(cairo);
    cairo_surface_destroy(surface);
    cairo_font_options_destroy(options);
    pango_font_description_free(description);
    g_object_unref(layout);
    return texture;
}

static CHyprColor configColor(Config::INTEGER color) {
    return CHyprColor{static_cast<uint64_t>(color)};
}

CHyprBar::CHyprBar(PHLWINDOW pWindow) : IHyprWindowDecoration(pWindow) {
    m_pWindow = pWindow;

    const auto PMONITOR         = pWindow->m_monitor.lock();
    PMONITOR->m_scheduledRecalc = true;

    syncNativePolicy();

    // button events

    m_pTouchDownCallback   = Event::bus()->m_events.input.touch.down.listen([&](ITouch::SDownEvent e, Event::SCallbackInfo& info) { onTouchDown(info, e); });
    m_pTouchUpCallback     = Event::bus()->m_events.input.touch.up.listen([&](ITouch::SUpEvent e, Event::SCallbackInfo& info) { onTouchUp(info, e); });

    // move events
    m_pTouchMoveCallback = Event::bus()->m_events.input.touch.motion.listen([&](ITouch::SMotionEvent e, Event::SCallbackInfo& info) { onTouchMove(info, e); });


    Animation::mgr()->createAnimation(configColor(g_pGlobalState->config.barColor->value()), m_cRealBarColor, Config::animationTree()->getAnimationPropertyConfig("border"),
                                      pWindow, AVARDAMAGE_NONE);
    m_cRealBarColor->setUpdateCallback([&](auto) { damageEntire(); });
}

CHyprBar::~CHyprBar() {
    if (m_ownsMaximizePolicy && m_pWindow) m_pWindow->m_suppressedEvents &= ~Desktop::View::SUPPRESS_MAXIMIZE;
    std::erase(g_pGlobalState->bars, m_self);
}

SDecorationPositioningInfo CHyprBar::getPositioningInfo() {
    const auto                 HEIGHT     = g_pGlobalState->config.barHeight->value();
    const auto                 ENABLED    = g_pGlobalState->config.enabled->value();
    const auto                 PRECEDENCE = g_pGlobalState->config.barPrecedenceOverBorder->value();

    SDecorationPositioningInfo info;
    info.policy         = m_hidden ? DECORATION_POSITION_ABSOLUTE : DECORATION_POSITION_STICKY;
    info.edges          = DECORATION_EDGE_TOP;
    info.priority       = PRECEDENCE ? 10005 : 5000;
    info.reserved       = true;
    info.desiredExtents = {{0, m_hidden || !ENABLED ? 0 : HEIGHT}, {0, 0}};
    return info;
}

void CHyprBar::onPositioningReply(const SDecorationPositioningReply& reply) {
    if (reply.assignedGeometry.size() != m_bAssignedBox.size())
        m_bWindowSizeChanged = true;

    m_bAssignedBox = reply.assignedGeometry;
}

std::string CHyprBar::getDisplayName() {
    return "Hyprbar";
}

bool CHyprBar::inputIsValid() {
    // HYPRSTACK_INPUT_GUARD: no invisible hitbox over tiled client tabs.
    if (m_hidden || !g_pGlobalState->config.enabled->value() || !validMapped(m_pWindow)) {
        m_bDragPending = false;
        m_bCancelledDown = false;
        return false;
    }

    if (g_pSeatManager->m_seatGrab && !g_pSeatManager->m_seatGrab->accepts(m_pWindow->wlSurface()->resource()))
        return false;

    const auto MOUSE    = g_pInputManager->getMouseCoordsInternal();
    auto       PMONITOR = Desktop::focusState()->monitor();

    if (!PMONITOR)
        return false;

    Desktop::CViewHitTester hitTester{*Desktop::viewState()};

    const auto              WINDOWATCURSOR = hitTester.windowAt(MOUSE, Desktop::View::RESERVED_EXTENTS | Desktop::View::INPUT_EXTENTS | Desktop::View::ALLOW_FLOATING);

    auto                    focusState = Desktop::focusState();
    auto                    window     = focusState->window();

    if (WINDOWATCURSOR != m_pWindow && !m_bDraggingThis)
        return false;

    PHLLS    foundSurface = nullptr;
    Vector2D surfaceCoords;

    // Check Top Layer
    hitTester.layerSurfaceAt(MOUSE, &PMONITOR->m_layerSurfaceLayers[ZWLR_LAYER_SHELL_V1_LAYER_TOP], &surfaceCoords, &foundSurface);
    if (foundSurface)
        return false;

    // Check Overlay Layer
    hitTester.layerSurfaceAt(MOUSE, &PMONITOR->m_layerSurfaceLayers[ZWLR_LAYER_SHELL_V1_LAYER_OVERLAY], &surfaceCoords, &foundSurface);
    if (foundSurface)
        return false;

    return true;
}

static WP<CHyprBar> pointerBar(Vector2D pos) {
    const auto window = Desktop::viewState()->hitTest().windowAt(pos,
        Desktop::View::ALLOW_FLOATING | Desktop::View::RESERVED_EXTENTS | Desktop::View::INPUT_EXTENTS);
    if (!validMapped(window) || Fullscreen::controller()->getFullscreenModes(window).internal == Fullscreen::FSMODE_FULLSCREEN) return {};
    for (const auto& decoration : window->m_windowDecorations)
        if (auto* bar = dynamic_cast<CHyprBar*>(decoration.get())) return bar->m_self;
    return {};
}
void CHyprBar::dispatchPointerMove(Vector2D pos, Event::SCallbackInfo& info) {
    if (!g_pGlobalState) return;
    auto& hovered = g_pGlobalState->pointerHovered;
    auto& pressed = g_pGlobalState->pointerPressed;
    if (!g_pGlobalState->config.enabled->value() || g_pInputManager->isConstrained() || g_pSessionLockManager->isSessionLocked()) {
        if (hovered && hovered->m_iButtonHoverState) { hovered->m_iButtonHoverState=0; hovered->damageEntire(); }
        hovered.reset(); pressed.reset(); return;
    }
    if (pressed) { pressed->onMouseMove(pos); return; }
    const auto current = info.cancelled ? WP<CHyprBar>{} : pointerBar(pos);
    if (hovered != current && hovered) { hovered->m_iButtonHoverState=0; hovered->m_bButtonHovered=false; hovered->damageEntire(); }
    hovered=current;
    if (hovered) hovered->onMouseMove(pos);
}
void CHyprBar::dispatchPointerButton(IPointer::SButtonEvent event, Event::SCallbackInfo& info) {
    if (!g_pGlobalState || !g_pGlobalState->config.enabled->value() || g_pInputManager->isConstrained() || g_pSessionLockManager->isSessionLocked()) return;
    auto& pressed = g_pGlobalState->pointerPressed;
    if (event.state == WL_POINTER_BUTTON_STATE_PRESSED) {
        if (info.cancelled) return;
        pressed=pointerBar(g_pInputManager->getMouseCoordsInternal());
        if (pressed) pressed->onMouseButton(info,event);
    } else {
        if (pressed) pressed->onMouseButton(info,event);
        pressed.reset();
    }
}

void CHyprBar::onMouseButton(Event::SCallbackInfo& info, IPointer::SButtonEvent e) {
    if (!inputIsValid())
        return;

    if (e.state != WL_POINTER_BUTTON_STATE_PRESSED) {
        handleUpEvent(info);
        return;
    }

    handleDownEvent(info, std::nullopt);
}

void CHyprBar::onTouchDown(Event::SCallbackInfo& info, ITouch::SDownEvent e) {
    // Don't do anything if you're already grabbed a window with another finger
    if (!inputIsValid() || e.touchID != 0)
        return;

    handleDownEvent(info, e);
}

void CHyprBar::onTouchUp(Event::SCallbackInfo& info, ITouch::SUpEvent e) {
    if (!m_bDragPending || !m_bTouchEv || e.touchID != m_touchId)
        return;

    handleUpEvent(info);
}

void CHyprBar::onMouseMove(Vector2D coords) {
    if (m_hidden || !g_pGlobalState->config.enabled->value()) {
        m_bDragPending = false;
        return;
    }
    // ensure proper redraws of button icons on hover when using hardware cursors
    damageOnButtonHover();

    if (!m_bDragPending || m_bTouchEv || !validMapped(m_pWindow) || m_touchId != 0)
        return;

    m_bDragPending = false;
    handleMovement();
}

void CHyprBar::onTouchMove(Event::SCallbackInfo& info, ITouch::SMotionEvent e) {
    if (!m_bDragPending || !m_bTouchEv || !validMapped(m_pWindow) || e.touchID != m_touchId)
        return;

    auto PMONITOR     = m_pWindow->m_monitor.lock();
    PMONITOR          = PMONITOR ? PMONITOR : Desktop::focusState()->monitor();
    const auto COORDS = Vector2D(PMONITOR->m_position.x + e.pos.x * PMONITOR->m_size.x, PMONITOR->m_position.y + e.pos.y * PMONITOR->m_size.y);

    if (!m_bDraggingThis) {
        // Initial setup for dragging a window.
        g_pKeybindManager->m_dispatchers["setfloating"]("activewindow");
        g_pKeybindManager->m_dispatchers["resizewindowpixel"]("exact 50% 50%,activewindow");
        // pin it so you can change workspaces while dragging a window
        g_pKeybindManager->m_dispatchers["pin"]("activewindow");
    }
    g_pKeybindManager->m_dispatchers["movewindowpixel"](std::format("exact {} {},activewindow", (int)(COORDS.x - (assignedBoxGlobal().w / 2)), (int)COORDS.y));
    m_bDraggingThis = true;
}

void CHyprBar::handleDownEvent(Event::SCallbackInfo& info, std::optional<ITouch::SDownEvent> touchEvent) {
    m_bTouchEv = touchEvent.has_value();
    if (m_bTouchEv)
        m_touchId = touchEvent.value().touchID;

    const auto PWINDOW = m_pWindow.lock();

    auto       COORDS = cursorRelativeToBar();
    if (m_bTouchEv) {
        ITouch::SDownEvent e        = touchEvent.value();
        PHLMONITOR         PMONITOR = nullptr;
        for (auto& m : State::monitorState()->monitors()) {
            if (m->m_name == (!e.device->m_boundOutput.empty() ? e.device->m_boundOutput : "")) {
                PMONITOR = m;
                break;
            }
        }
        PMONITOR = PMONITOR ? PMONITOR : Desktop::focusState()->monitor();
        COORDS   = Vector2D(PMONITOR->m_position.x + e.pos.x * PMONITOR->m_size.x, PMONITOR->m_position.y + e.pos.y * PMONITOR->m_size.y) - assignedBoxGlobal().pos();
    }

    const auto HEIGHT           = g_pGlobalState->config.barHeight->value();
    const auto BARBUTTONPADDING = g_pGlobalState->config.barButtonPadding->value();
    const auto BARPADDING       = g_pGlobalState->config.barPadding->value();
    const auto ALIGNBUTTONS     = g_pGlobalState->config.barButtonsAlignment->value();
    const auto ON_DOUBLE_CLICK  = g_pGlobalState->config.onDoubleClick->value();

    const bool BUTTONSRIGHT = ALIGNBUTTONS != "left";

    if (!VECINRECT(COORDS, 0, 0, assignedBoxGlobal().w, HEIGHT - 1)) {

        if (m_bDraggingThis) {
            if (m_bTouchEv)
                g_pKeybindManager->m_dispatchers["settiled"]("activewindow");
            g_pKeybindManager->m_dispatchers["mouse"]("0movewindow");
            Log::logger->log(Log::DEBUG, "[hyprbars] Dragging ended on {:x}", (uintptr_t)PWINDOW.get());
        }

        m_bDraggingThis = false;
        m_bDragPending  = false;
        m_bTouchEv      = false;
        return;
    }

    if (Desktop::focusState()->window() != PWINDOW)
        Desktop::focusState()->fullWindowFocus(PWINDOW, Desktop::FOCUS_REASON_CLICK);

    if (PWINDOW->m_isFloating)
        Desktop::windowState()->raise(PWINDOW);

    info.cancelled   = true;
    m_bCancelledDown = true;

    if (doButtonPress(BARPADDING, BARBUTTONPADDING, HEIGHT, COORDS, BUTTONSRIGHT))
        return;

    if (!ON_DOUBLE_CLICK.empty() &&
        std::chrono::duration_cast<std::chrono::milliseconds>(Time::steadyNow() - m_lastMouseDown).count() < 400 /* Arbitrary delay I found suitable */) {
        if (!runDecorationAction(m_pWindow.lock(), "maximize"))
            Config::Supplementary::executor()->spawn("env HYPRSTACK_WINDOW_ADDRESS=" + std::format("0x{:x}", reinterpret_cast<uintptr_t>(m_pWindow.lock().get())) + " HYPRSTACK_WINDOW_ID=" + std::format("{:x}", m_pWindow->m_stableID) + " " + ON_DOUBLE_CLICK);
        m_bDragPending = false;
    } else {
        m_lastMouseDown = Time::steadyNow();
        m_bDragPending  = true;
    }
}

void CHyprBar::handleUpEvent(Event::SCallbackInfo& info) {
    if (m_pWindow.lock() != Desktop::focusState()->window())
        return;

    if (m_bCancelledDown)
        info.cancelled = true;

    m_bCancelledDown = false;

    if (m_bDraggingThis) {
        g_pKeybindManager->changeMouseBindMode(MBIND_INVALID);
        m_bDraggingThis = false;
        if (m_bTouchEv)
            (void)Config::Actions::floatWindow(Config::Actions::eTogglableAction::TOGGLE_ACTION_DISABLE);

        Log::logger->log(Log::DEBUG, "[hyprbars] Dragging ended on {:x}", (uintptr_t)m_pWindow.lock().get());
    }

    m_bDragPending = false;
    m_bTouchEv     = false;
    m_touchId      = 0;
}

void CHyprBar::handleMovement() {
    g_pKeybindManager->changeMouseBindMode(MBIND_MOVE);
    m_bDraggingThis = true;
    Log::logger->log(Log::DEBUG, "[hyprbars] Dragging initiated on {:x}", (uintptr_t)m_pWindow.lock().get());
    return;
}

bool CHyprBar::doButtonPress(Config::INTEGER barPadding, Config::INTEGER barButtonPadding, Config::INTEGER barHeight, Vector2D COORDS, const bool BUTTONSRIGHT) {
    //check if on a button
    float offset = barPadding;

    for (auto& b : g_pGlobalState->buttons) {
        const auto BARBUF     = Vector2D{(int)assignedBoxGlobal().w, barHeight};
        Vector2D   currentPos = Vector2D{(BUTTONSRIGHT ? BARBUF.x - b.size - offset : offset), (BARBUF.y - b.size) / 2.0}.floor();

        if (VECINRECT(COORDS, currentPos.x, currentPos.y, currentPos.x + b.size, currentPos.y + b.size)) {
            // hit on close
            if (!b.icon.starts_with("hyprstack:") || !runDecorationAction(m_pWindow.lock(), b.icon.substr(10)))
                g_pKeybindManager->m_dispatchers["exec"]("env HYPRSTACK_WINDOW_ADDRESS=" + std::format("0x{:x}", reinterpret_cast<uintptr_t>(m_pWindow.lock().get())) + " HYPRSTACK_WINDOW_ID=" + std::format("{:x}", m_pWindow->m_stableID) + " " + b.cmd);
            return true;
        }

        offset += barButtonPadding + b.size;
    }
    return false;
}

void CHyprBar::renderBarTitle(const Vector2D& bufferSize, const float scale) {
    const auto COLORVAL         = g_pGlobalState->config.textColor->value();
    const auto SIZE             = g_pGlobalState->config.barTextSize->value();
    const auto WEIGHT           = g_pGlobalState->config.barTextWeight->value();
    const auto FONT             = g_pGlobalState->config.barTextFont->value();
    const auto ALIGN            = g_pGlobalState->config.barTextAlign->value();
    const auto BARPADDING       = g_pGlobalState->config.barPadding->value();
    const auto BARBUTTONPADDING = g_pGlobalState->config.barButtonPadding->value();

    float      buttonSizes = BARBUTTONPADDING;
    for (auto& b : g_pGlobalState->buttons) {
        buttonSizes += b.size + BARBUTTONPADDING;
    }

    const int  scaledSize        = std::round(SIZE * scale);
    const auto scaledButtonsSize = buttonSizes * scale;
    const auto scaledBarPadding  = BARPADDING * scale;
    const int  paddingTotal      = scaledBarPadding * 2 + scaledButtonsSize + (ALIGN != "left" ? scaledButtonsSize : 0);
    const int  maxWidth          = std::clamp(static_cast<int>(bufferSize.x - paddingTotal), 0, INT_MAX);

    if (m_szLastTitle.empty() || maxWidth < 1) {
        m_pTextTex = nullptr;
        return;
    }

    const CHyprColor COLOR = m_bForcedTitleColor.value_or(configColor(COLORVAL));
    // HYPRSTACK_SRGB_GLYPHS: Cairo textures belong to the decoration, not
    // the client's color-managed surface. LCD antialiasing is unsuitable for
    // composited HDR textures and produces colored fringes on the glyphs.
    m_pTextTex = renderDecorationText(m_szLastTitle, COLOR, scaledSize, FONT, maxWidth, WEIGHT.m_value);
}

size_t CHyprBar::getVisibleButtonCount(Config::INTEGER barButtonPadding, Config::INTEGER barPadding, const Vector2D& bufferSize, const float scale) {
    float  availableSpace = bufferSize.x - barPadding * scale * 2;
    size_t count          = 0;

    for (const auto& button : g_pGlobalState->buttons) {
        const float buttonSpace = (button.size + barButtonPadding) * scale;
        if (availableSpace >= buttonSpace) {
            count++;
            availableSpace -= buttonSpace;
        } else
            break;
    }

    return count;
}

void CHyprBar::renderBarButtons(CBox* barBox, const float scale, const float a) {
    const auto BARBUTTONPADDING = g_pGlobalState->config.barButtonPadding->value();
    const auto BARPADDING       = g_pGlobalState->config.barPadding->value();
    const auto ALIGNBUTTONS     = g_pGlobalState->config.barButtonsAlignment->value();
    const auto INACTIVECOLOR    = g_pGlobalState->config.inactiveButtonColor->value();

    const bool BUTTONSRIGHT    = ALIGNBUTTONS != "left";
    const auto visibleCount    = getVisibleButtonCount(BARBUTTONPADDING, BARPADDING, Vector2D{barBox->w, barBox->h}, scale);
    const bool INVALIDATEICONS = m_bButtonsDirty || m_bWindowSizeChanged;

    int        offset = BARPADDING * scale;
    for (size_t i = 0; i < visibleCount; ++i) {
        auto&      button           = g_pGlobalState->buttons[i];
        const auto scaledButtonSize = button.size * scale;
        const auto scaledButtonsPad = BARBUTTONPADDING * scale;

        auto       color = button.bgcol;

        if (INACTIVECOLOR > 0) {
            color = m_bWindowHasFocus ? color : configColor(INACTIVECOLOR);
            if (INVALIDATEICONS && button.userfg && button.iconTex)
                button.iconTex = nullptr;
        }

        color.a *= a;

        CBox buttonBox = {barBox->x + (BUTTONSRIGHT ? barBox->w - offset - scaledButtonSize : offset), barBox->y + (barBox->h - scaledButtonSize) / 2.0, scaledButtonSize,
                          scaledButtonSize};
        buttonBox.round();

        // Traffic-light circles are rendered as sRGB textures with their glyphs.
        if (!button.icon.starts_with("hyprstack:"))
            g_pHyprOpenGL->renderRect(buttonBox, color, {.round = static_cast<int>(4 * scale), .roundingPower = 2.F});

        offset += scaledButtonsPad + scaledButtonSize;
    }
}

void CHyprBar::renderBarButtonsText(CBox* barBox, const float scale, const float a) {
    const auto HEIGHT           = g_pGlobalState->config.barHeight->value();
    const auto BARBUTTONPADDING = g_pGlobalState->config.barButtonPadding->value();
    const auto BARPADDING       = g_pGlobalState->config.barPadding->value();
    const auto ALIGNBUTTONS     = g_pGlobalState->config.barButtonsAlignment->value();
    const auto ICONONHOVER      = g_pGlobalState->config.iconOnHover->value();

    const bool BUTTONSRIGHT = ALIGNBUTTONS != "left";
    const auto visibleCount = getVisibleButtonCount(BARBUTTONPADDING, BARPADDING, Vector2D{barBox->w, barBox->h}, scale);
    const auto COORDS       = cursorRelativeToBar();

    int        offset        = BARPADDING * scale;
    float      noScaleOffset = BARPADDING;

    for (size_t i = 0; i < visibleCount; ++i) {
        auto&      button           = g_pGlobalState->buttons[i];
        const auto scaledButtonSize = button.size * scale;
        const auto scaledButtonsPad = BARBUTTONPADDING * scale;

        // check if hovering here
        const auto BARBUF     = Vector2D{(int)assignedBoxGlobal().w, HEIGHT};
        Vector2D   currentPos = Vector2D{(BUTTONSRIGHT ? BARBUF.x - button.size - noScaleOffset : noScaleOffset), (BARBUF.y - button.size) / 2.0}.floor();
        bool       hovering   = VECINRECT(COORDS, currentPos.x, currentPos.y, currentPos.x + button.size, currentPos.y + button.size);
        noScaleOffset += BARBUTTONPADDING + button.size;

        if (button.icon.starts_with("hyprstack:")) {
            auto symbol = button.icon.substr(10);
            if (symbol == "maximize" && Fullscreen::controller()->getFullscreenModes(m_pWindow.lock()).client == Fullscreen::FSMODE_MAXIMIZED)
                symbol = "restore";
            const int pixels = std::max(1, static_cast<int>(std::round(16 * scale)));
            auto background = button.bgcol;
            background.a *= m_bWindowHasFocus ? 1.F : 0.65F;
            const auto key = std::format("{}:{}:{}:{}:{}:{}:{}:{}", symbol, pixels, hovering,
                background.r, background.g, background.b, background.a, button.fgcol.r);
            auto& icon = m_controlIcons[key];
            if (!icon) icon = renderDecorationControl(symbol, button.fgcol, background, pixels, hovering);
            CBox box{barBox->x + (BUTTONSRIGHT ? barBox->w - offset - scaledButtonSize / 2.0 : offset + scaledButtonSize / 2.0) - pixels / 2.0,
                barBox->y + barBox->h / 2.0 - pixels / 2.0, pixels, pixels};
            g_pHyprOpenGL->renderTexture(icon, box.round(), {.a = a, .allowDim = false});
            offset += scaledButtonsPad + scaledButtonSize;
            continue;
        }

        if ((!button.iconTex || button.iconTex->m_texID == 0) && !button.icon.empty()) {
            // render icon
            auto fgcol = button.userfg ? button.fgcol : (button.bgcol.r + button.bgcol.g + button.bgcol.b < 1) ? CHyprColor(0xFFFFFFFF) : CHyprColor(0xFF000000);

            button.iconTex = renderDecorationText(button.icon, fgcol,
                std::round(button.size * 0.62 * scale), "Noto Sans", scaledButtonSize);
        }

        if (!button.iconTex || button.iconTex->m_texID == 0)
            continue;

        const auto iconX = barBox->x + (BUTTONSRIGHT ? barBox->width - offset - scaledButtonSize / 2.0 : offset + scaledButtonSize / 2.0) - button.iconTex->m_size.x / 2.0;
        const auto iconY = barBox->y + barBox->height / 2.0 - button.iconTex->m_size.y / 2.0;
        CBox       pos   = {iconX, iconY, button.iconTex->m_size.x, button.iconTex->m_size.y};

        if (!ICONONHOVER || (ICONONHOVER && m_iButtonHoverState > 0))
            g_pHyprOpenGL->renderTexture(button.iconTex, pos.round(), {.a = a, .allowDim = false});
        offset += scaledButtonsPad + scaledButtonSize;

        bool currentBit = (m_iButtonHoverState & (1 << i)) != 0;
        if (hovering != currentBit) {
            m_iButtonHoverState ^= (1 << i);
            // damage to get rid of some artifacts when icons are "hidden"
            damageEntire();
        }
    }
}

void CHyprBar::draw(PHLMONITOR pMonitor, const float& a) {
    const auto ENABLED = g_pGlobalState->config.enabled->value();

    if (m_bLastEnabledState != ENABLED) {
        m_bLastEnabledState = ENABLED;
        g_pDecorationPositioner->repositionDeco(this);
    }

    if (m_hidden || !validMapped(m_pWindow) || !ENABLED)
        return;

    const auto PWINDOW = m_pWindow.lock();
    if (Fullscreen::controller()->getFullscreenModes(PWINDOW).internal == Fullscreen::FSMODE_FULLSCREEN) return;

    if (!PWINDOW->m_ruleApplicator->decorate().valueOrDefault())
        return;

    auto data = CBarPassElement::SBarData{this, a};
    g_pHyprRenderer->addPassElement(makeUnique<CBarPassElement>(data));
}

extern bool hyprstackOverviewRendering();

void CHyprBar::renderPass(PHLMONITOR pMonitor, const float& a) {
    const auto  PWINDOW = m_pWindow.lock();

    static auto PENABLEBLURGLOBAL = CConfigValue<Config::BOOL>("decoration:blur:enabled");
    const auto  BARCOLOR          = g_pGlobalState->config.barColor->value();
    const auto  HEIGHT            = g_pGlobalState->config.barHeight->value();
    const auto  PRECEDENCE        = g_pGlobalState->config.barPrecedenceOverBorder->value();
    const auto  ALIGNBUTTONS      = g_pGlobalState->config.barButtonsAlignment->value();
    const auto  ENABLETITLE       = g_pGlobalState->config.barTitleEnabled->value();
    const auto  ENABLEBLUR        = g_pGlobalState->config.barBlur->value();
    const auto  INACTIVECOLOR     = g_pGlobalState->config.inactiveButtonColor->value();

    if (INACTIVECOLOR > 0) {
        bool currentWindowFocus = PWINDOW == Desktop::focusState()->window();
        if (currentWindowFocus != m_bWindowHasFocus) {
            m_bWindowHasFocus = currentWindowFocus;
            m_bButtonsDirty   = true;
        }
    }

    const CHyprColor DEST_COLOR = m_bForcedBarColor.value_or(configColor(BARCOLOR));
    if (DEST_COLOR != m_cRealBarColor->goal())
        *m_cRealBarColor = DEST_COLOR;

    CHyprColor color = m_cRealBarColor->value();

    color.a *= a;
    const bool BUTTONSRIGHT = ALIGNBUTTONS != "left";
    const bool SHOULDBLUR   = ENABLEBLUR && *PENABLEBLURGLOBAL && color.a < 1.F;

    if (HEIGHT < 1) {
        m_iLastHeight = HEIGHT;
        return;
    }

    const auto PWORKSPACE      = PWINDOW->m_workspace;
    const auto WORKSPACEOFFSET = PWORKSPACE && !PWINDOW->m_pinned ? PWORKSPACE->m_renderOffset->value() : Vector2D();

    const auto ROUNDING = PWINDOW->rounding() + (PRECEDENCE ? 0 : PWINDOW->getRealBorderSize());

    const auto scaledRounding = ROUNDING > 0 ? ROUNDING * pMonitor->m_scale - 2 /* idk why but otherwise it looks bad due to the gaps */ : 0;

    m_seExtents = {{0, HEIGHT}, {}};

    const auto DECOBOX = assignedBoxGlobal();

    const auto BARBUF = DECOBOX.size() * pMonitor->m_scale;

    CBox       titleBarBox = {DECOBOX.x - pMonitor->m_position.x, DECOBOX.y - pMonitor->m_position.y, DECOBOX.w,
                              DECOBOX.h + ROUNDING * 3 /* to fill the bottom cuz we can't disable rounding there */};

    titleBarBox.translate(PWINDOW->m_floatingOffset).scale(pMonitor->m_scale).round();

    if (titleBarBox.w < 1 || titleBarBox.h < 1)
        return;

    auto scissorBox = titleBarBox;
    if (hyprstackOverviewRendering())
        g_pHyprRenderer->m_renderData.renderModif.applyToBox(scissorBox);
    g_pHyprOpenGL->scissor(scissorBox);

    if (ROUNDING) {
        // the +1 is a shit garbage temp fix until renderRect supports an alpha matte
        CBox windowBox = {PWINDOW->position(Desktop::View::IGeometric::GEOMETRIC_CURRENT).x + PWINDOW->m_floatingOffset.x - pMonitor->m_position.x + 1,
                          PWINDOW->position(Desktop::View::IGeometric::GEOMETRIC_CURRENT).y + PWINDOW->m_floatingOffset.y - pMonitor->m_position.y + 1,
                          PWINDOW->size(Desktop::View::IGeometric::GEOMETRIC_CURRENT).x - 2, PWINDOW->size(Desktop::View::IGeometric::GEOMETRIC_CURRENT).y - 2};

        if (windowBox.w < 1 || windowBox.h < 1)
            return;

        glClearStencil(0);
        glClear(GL_STENCIL_BUFFER_BIT);

        g_pHyprOpenGL->setCapStatus(GL_STENCIL_TEST, true);

        glStencilFunc(GL_ALWAYS, 1, -1);
        glStencilOp(GL_KEEP, GL_KEEP, GL_REPLACE);

        glColorMask(GL_FALSE, GL_FALSE, GL_FALSE, GL_FALSE);

        windowBox.translate(WORKSPACEOFFSET).scale(pMonitor->m_scale).round();
        g_pHyprOpenGL->renderRect(windowBox, CHyprColor(0, 0, 0, 0), {.round = scaledRounding, .roundingPower = m_pWindow->roundingPower()});
        glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);

        glStencilFunc(GL_NOTEQUAL, 1, -1);
        glStencilOp(GL_KEEP, GL_KEEP, GL_REPLACE);
    }

    if (SHOULDBLUR)
        g_pHyprOpenGL->renderRect(titleBarBox, color, {.round = scaledRounding, .roundingPower = m_pWindow->roundingPower(), .blur = true, .blurA = a});
    else
        g_pHyprOpenGL->renderRect(titleBarBox, color, {.round = scaledRounding, .roundingPower = m_pWindow->roundingPower()});

    // render title
    if (ENABLETITLE && (m_szLastTitle != PWINDOW->m_title || m_bWindowSizeChanged || !m_pTextTex || m_pTextTex->m_texID == 0 || m_bTitleColorChanged)) {
        m_szLastTitle = PWINDOW->m_title;
        renderBarTitle(BARBUF, pMonitor->m_scale);
    }

    if (ROUNDING) {
        // cleanup stencil
        glClearStencil(0);
        glClear(GL_STENCIL_BUFFER_BIT);
        g_pHyprOpenGL->setCapStatus(GL_STENCIL_TEST, false);
        glStencilMask(-1);
        glStencilFunc(GL_ALWAYS, 1, 0xFF);
    }

    CBox textBox = {titleBarBox.x, titleBarBox.y, (int)BARBUF.x, (int)BARBUF.y};
    if (ENABLETITLE && m_pTextTex) {
        const auto BARPADDING       = g_pGlobalState->config.barPadding->value();
        const auto BARBUTTONPADDING = g_pGlobalState->config.barButtonPadding->value();
        const auto ALIGN            = g_pGlobalState->config.barTextAlign->value();

        float      buttonSizes = BARBUTTONPADDING;
        for (auto& b : g_pGlobalState->buttons) {
            buttonSizes += b.size + BARBUTTONPADDING;
        }

        const auto scaledBorderSize  = PWINDOW->getRealBorderSize() * pMonitor->m_scale;
        const auto scaledButtonsSize = buttonSizes * pMonitor->m_scale;
        const auto scaledBarPadding  = BARPADDING * pMonitor->m_scale;
        const auto xOffset           = ALIGN == "left" ? std::round(scaledBarPadding + (BUTTONSRIGHT ? 0 : scaledButtonsSize)) :
                                                         std::round(((BARBUF.x - scaledBorderSize) / 2.0 - m_pTextTex->m_size.x / 2.0));
        const auto yOffset           = std::round((BARBUF.y - m_pTextTex->m_size.y) / 2.0);
        CBox       titleBox          = {textBox.x + xOffset, textBox.y + yOffset, m_pTextTex->m_size.x, m_pTextTex->m_size.y};

        titleBox.round(); // Keep rasterized glyphs on physical pixels.
        g_pHyprOpenGL->renderTexture(m_pTextTex, titleBox, {.a = a, .allowDim = false});
    }

    renderBarButtons(&textBox, pMonitor->m_scale, a);
    m_bButtonsDirty = false;

    g_pHyprOpenGL->scissor(nullptr);

    renderBarButtonsText(&textBox, pMonitor->m_scale, a);

    m_bWindowSizeChanged = false;
    m_bTitleColorChanged = false;

    // dynamic updates change the extents
    if (m_iLastHeight != HEIGHT) {
        PWINDOW->layoutTarget()->recalc();
        m_iLastHeight = HEIGHT;
    }
}

eDecorationType CHyprBar::getDecorationType() {
    return DECORATION_CUSTOM;
}

void CHyprBar::updateWindow(PHLWINDOW pWindow) {
    damageEntire();
}

// HYPRSTACK_ATOMIC_STACKING: reserve title extents before restoring geometry.
void CHyprBar::syncNativePolicy() {
    const auto window = m_pWindow.lock();
    if (!window) return;
    // HYPRSTACK_CSD_STATE: xdg-shell initially marks every mapped window
    // maximized to hide tiled CSD. A normal stacking window must explicitly
    // clear that flag even when fullscreen_state(0, 0) is a controller no-op.
    const bool stacking = g_pGlobalState->config.enabled->value();
    // GTK4 hides its minimize button unless xdg-shell advertises it. Use
    // public Wayland resource iteration instead of reaching into private
    // Hyprland protocol fields. Capabilities precede the next configure.
    if (window->m_xdgSurface && window->m_xdgSurface->m_toplevel && m_nativeMinimizeCapability != stacking) {
        auto* toplevel = window->m_xdgSurface->m_toplevel.get();
        struct Capabilities { CXDGToplevelResource* target; bool minimize; } data{toplevel, stacking};
        wl_client_for_each_resource(window->resource()->client(), [](wl_resource* resource, void* raw) {
            auto* data = static_cast<Capabilities*>(raw);
            if (std::string_view(wl_resource_get_class(resource)) != "xdg_toplevel" ||
                wl_resource_get_version(resource) < 5 || CXDGToplevelResource::fromResource(resource).get() != data->target)
                return WL_ITERATOR_CONTINUE;
            uint32_t values[]{XDG_TOPLEVEL_WM_CAPABILITIES_FULLSCREEN, XDG_TOPLEVEL_WM_CAPABILITIES_MAXIMIZE,
                XDG_TOPLEVEL_WM_CAPABILITIES_MINIMIZE};
            wl_array array{sizeof(uint32_t) * (data->minimize ? 3U : 2U), sizeof(values), values};
            static_cast<CXdgToplevel*>(wl_resource_get_user_data(resource))->sendWmCapabilities(&array);
            return WL_ITERATOR_STOP;
        }, &data);
        m_nativeMinimizeCapability = stacking;
    }
    // HYPRSTACK_SCROLLING_MAXIMIZE_POLICY: clients such as Kitty remember
    // the synthetic tiled maximize flag and request it on their next map.
    // Column width owns maximize in tiling; native requests belong to floats.
    if (stacking || !window->m_isFloating) {
        if (!(window->m_suppressedEvents & Desktop::View::SUPPRESS_MAXIMIZE)) m_ownsMaximizePolicy = true;
        window->m_suppressedEvents |= Desktop::View::SUPPRESS_MAXIMIZE;
    } else if (m_ownsMaximizePolicy) {
        window->m_suppressedEvents &= ~Desktop::View::SUPPRESS_MAXIMIZE;
        m_ownsMaximizePolicy = false;
    }
    // Reassert the synthetic flag only for tiles. Normal floating Qt windows
    // must clear it too, so fullscreen exit restores their windowed geometry.
    const auto client = Fullscreen::controller()->getFullscreenModes(window).client;
    const bool maximized = client == Fullscreen::FSMODE_MAXIMIZED || (!stacking && !window->m_isFloating);
    if (window->m_xdgSurface && window->m_xdgSurface->m_toplevel)
        window->m_xdgSurface->m_toplevel->setMaximized(maximized);
    else if (window->m_xwaylandSurface && window->m_xwaylandSurface->m_maximized != maximized) {
        // Hyprland's client-only fullscreen_state does not update EWMH's
        // maximize bit. Keep toggle requests and the client's restore glyph
        // in sync; setMinimized republishes state without changing its value.
        window->m_xwaylandSurface->m_maximized = maximized;
        window->m_xwaylandSurface->setMinimized(window->m_xwaylandSurface->m_minimized);
    }
}

void CHyprBar::onConfigReloaded() {
    syncNativePolicy();
    m_bLastEnabledState = g_pGlobalState->config.enabled->value();
    m_iLastHeight = g_pGlobalState->config.barHeight->value();
    m_bButtonsDirty      = true;
    m_bTitleColorChanged = true;
    m_pTextTex           = nullptr;

    g_pDecorationPositioner->repositionDeco(this);
    damageEntire();
}

void CHyprBar::damageEntire() {
    g_pHyprRenderer->damageBox(assignedBoxGlobal());
}

Vector2D CHyprBar::cursorRelativeToBar() {
    return g_pInputManager->getMouseCoordsInternal() - assignedBoxGlobal().pos();
}

eDecorationLayer CHyprBar::getDecorationLayer() {
    return DECORATION_LAYER_UNDER;
}

uint64_t CHyprBar::getDecorationFlags() {
    return DECORATION_ALLOWS_MOUSE_INPUT | (g_pGlobalState->config.barPartOfWindow->value() ? DECORATION_PART_OF_MAIN_WINDOW : 0);
}

CBox CHyprBar::assignedBoxGlobal() {
    if (!validMapped(m_pWindow))
        return {};

    CBox box = m_bAssignedBox;
    box.translate(g_pDecorationPositioner->getEdgeDefinedPoint(DECORATION_EDGE_TOP, m_pWindow.lock()));

    const auto PWORKSPACE      = m_pWindow->m_workspace;
    const auto WORKSPACEOFFSET = PWORKSPACE && !m_pWindow->m_pinned ? PWORKSPACE->m_renderOffset->value() : Vector2D();

    return box.translate(WORKSPACEOFFSET);
}

PHLWINDOW CHyprBar::getOwner() {
    return m_pWindow.lock();
}

void CHyprBar::updateRules() {
    syncNativePolicy();
    const auto PWINDOW              = m_pWindow.lock();
    auto       prevHidden           = m_hidden;
    auto       prevForcedTitleColor = m_bForcedTitleColor;

    m_bForcedBarColor   = std::nullopt;
    m_bForcedTitleColor = std::nullopt;
    m_hidden            = false;

    if (PWINDOW->m_ruleApplicator->m_otherProps.props.contains(g_pGlobalState->nobarRuleIdx))
        m_hidden = truthy(PWINDOW->m_ruleApplicator->m_otherProps.props.at(g_pGlobalState->nobarRuleIdx)->effect);
    if (!PWINDOW->m_ruleApplicator->decorate().valueOrDefault()) m_hidden = true;
    if (PWINDOW->m_ruleApplicator->m_otherProps.props.contains(g_pGlobalState->barColorRuleIdx))
        m_bForcedBarColor = CHyprColor(Config::ParserUtils::parseColor(PWINDOW->m_ruleApplicator->m_otherProps.props.at(g_pGlobalState->barColorRuleIdx)->effect).value_or(0));
    if (PWINDOW->m_ruleApplicator->m_otherProps.props.contains(g_pGlobalState->titleColorRuleIdx))
        m_bForcedTitleColor = CHyprColor(Config::ParserUtils::parseColor(PWINDOW->m_ruleApplicator->m_otherProps.props.at(g_pGlobalState->titleColorRuleIdx)->effect).value_or(0));

    if (prevHidden != m_hidden)
        g_pDecorationPositioner->repositionDeco(this);
    if (prevForcedTitleColor != m_bForcedTitleColor)
        m_bTitleColorChanged = true;
}

void CHyprBar::damageOnButtonHover() {
    // HYPRSTACK_BUTTON_HOVER_BITS: a stable hover must not damage every frame.
    const auto padding = g_pGlobalState->config.barPadding->value();
    const auto spacing = g_pGlobalState->config.barButtonPadding->value();
    const auto height = g_pGlobalState->config.barHeight->value();
    const bool right = g_pGlobalState->config.barButtonsAlignment->value() != "left";
    const auto cursor = cursorRelativeToBar();
    unsigned int state = 0;
    float offset = padding;
    size_t index = 0;
    for (const auto& button : g_pGlobalState->buttons) {
        const CBox box{right ? assignedBoxGlobal().w - button.size - offset : offset,
            (height - button.size) / 2.0, button.size, button.size};
        if (box.containsPoint(cursor)) state |= 1U << index;
        offset += spacing + button.size;
        ++index;
    }
    if (state != m_iButtonHoverState) {
        m_iButtonHoverState = state;
        m_bButtonHovered = state != 0;
        damageEntire();
    }
}
