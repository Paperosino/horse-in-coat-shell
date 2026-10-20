#include "StickyWindows.hpp"
#include <cassert>
int main() {
    CanvasSticky::State state;
    const std::vector<CanvasSticky::Rect> peers{{200, 0, 100, 100}};
    // Keep a 20-unit gap to the left neighbour edge; acquire at 10 units.
    auto box = state.apply({85, 0, 100, 100}, peers, 20, 10, 30);
    assert(box.x == 80);
    box = state.apply({104, 0, 100, 100}, peers, 20, 10, 30);
    assert(box.x == 80);
    // Deliberate pressure releases the latch and permits overlap.
    box = state.apply({115, 0, 100, 100}, peers, 20, 10, 30);
    assert(box.x == 115);
    box = state.apply({87, 0, 100, 100}, peers, 20, 10, 30);
    assert(box.x == 87); // no immediate reattachment to the released edge
    state.apply({20, 0, 100, 100}, peers, 20, 10, 30);
    assert(state.apply({85, 0, 100, 100}, peers, 20, 10, 30).x == 80);
    assert(state.apply({85, 0, 100, 100}, {}, 20, 10, 30).x == 85);
    state = {};
    assert(state.apply({85, 500, 100, 100}, peers, 20, 10, 30).x == 85);
    state = {};
    assert(state.apply({105, 0, 100, 100}, peers, 0, 10, 30).x == 100);
}
