// Initial placement of managed floating windows, including XWayland dialogs.
#pragma once

#include <hyprland/src/desktop/state/WindowState.hpp>
#include <hyprland/src/desktop/view/Window.hpp>
#include <hyprland/src/desktop/Workspace.hpp>
#include <hyprland/src/layout/space/Space.hpp>
#include <hyprland/src/layout/target/WindowTarget.hpp>
#include <algorithm>
#include <fstream>
#include <sstream>

static PHLWINDOW telegramWebviewParent(PHLWINDOW window) {
    // Telegram's WebKit helper owns a separate, parentless toplevel. Identify
    // its process argument, so ordinary chats and arbitrary bot titles stay
    // ordinary windows. PPid ties it to the correct Telegram instance.
    const auto process = "/proc/" + std::to_string(window->getPID()) + "/";
    std::ifstream command(process + "cmdline", std::ios::binary);
    std::string argument;
    bool helper = false;
    while (std::getline(command, argument, '\0'))
        if (argument == "-webviewhelper") helper = true;
    if (!helper) return nullptr;

    std::ifstream status(process + "status");
    pid_t parentPID = 0;
    while (std::getline(status, argument)) {
        if (!argument.starts_with("PPid:")) continue;
        std::istringstream value(argument.substr(5));
        value >> parentPID;
        break;
    }
    if (parentPID <= 1) return nullptr;
    PHLWINDOW parent;
    for (const auto& candidate : Desktop::windowState()->windows()) {
        if (candidate == window || !candidate->m_isMapped || candidate->isHidden() ||
            candidate->getPID() != parentPID || !candidate->m_workspace || candidate->m_workspace->m_isSpecialWorkspace)
            continue;
        if (!parent || (parent->m_isFloating && !candidate->m_isFloating)) parent = candidate;
    }
    return parent;
}

static bool centerFloatingWindow(PHLWINDOW window, bool inferParent) {
    if (!window->m_isMapped || !window->m_isFloating || window->isX11OverrideRedirect() ||
        window->m_pinned || Fullscreen::controller()->isFullscreen(window) || !window->layoutTarget())
        return false;

    auto parent = window->parent();
    if (!parent && inferParent) parent = telegramWebviewParent(window);
    // Telegram's Linux auxiliary windows do not always set a transient parent.
    // Use the originating process, rather than another account on a different output.
    if (!parent && inferParent) {
        for (const auto& candidate : Desktop::windowState()->windows()) {
            if (candidate == window || !candidate->m_isMapped || candidate->isHidden() ||
                candidate->getPID() != window->getPID() || candidate->m_class != window->m_class ||
                !candidate->m_workspace || candidate->m_workspace->m_isSpecialWorkspace)
                continue;
            if (!parent || (parent->m_isFloating && !candidate->m_isFloating)) parent = candidate;
        }
    }
    if (parent && parent->layoutTarget() && parent->m_workspace && parent->m_workspace != window->m_workspace)
        window->layoutTarget()->assignToSpace(parent->layoutTarget()->space());

    const auto space = window->layoutTarget()->space();
    if (!space) return false;
    const auto work = space->workArea(true);
    const auto extents = window->getWindowExtentsUnified(Desktop::View::RESERVED_EXTENTS | Desktop::View::INPUT_EXTENTS);
    const auto available = work.size() - extents.topLeft - extents.bottomRight;
    if (available.x <= 0 || available.y <= 0) return false;
    const auto size = window->size(Desktop::View::IGeometric::GEOMETRIC_GOAL).clamp(Vector2D{1, 1}, available).floor();
    const auto position = (work.pos() + (work.size() - size - extents.topLeft - extents.bottomRight) / 2.0 + extents.topLeft).floor();
    window->layoutTarget()->setPositionGlobal(CBox{position, size});
    return true;
}
