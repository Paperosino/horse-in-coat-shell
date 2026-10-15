#pragma once

#include <qcolor.h>
#include <qlist.h>
#include <qobject.h>
#include <qqmlengine.h>

namespace hyprstack::blobs {

class BlobShape;
class BlobInvertedRect;

class BlobGroup : public QObject {
    Q_OBJECT
    QML_ELEMENT
    Q_PROPERTY(qreal smoothing READ smoothing WRITE setSmoothing NOTIFY smoothingChanged)
    Q_PROPERTY(QColor color READ color WRITE setColor NOTIFY colorChanged)
    Q_PROPERTY(bool cornerFill READ cornerFill WRITE setCornerFill NOTIFY cornerFillChanged)
    Q_PROPERTY(QColor shadowColor READ shadowColor WRITE setShadowColor NOTIFY shadowChanged)
    Q_PROPERTY(qreal shadowSize READ shadowSize WRITE setShadowSize NOTIFY shadowChanged)
    Q_PROPERTY(qreal shadowOffset READ shadowOffset WRITE setShadowOffset NOTIFY shadowChanged)

public:
    explicit BlobGroup(QObject* parent = nullptr);
    ~BlobGroup() override;

    [[nodiscard]] qreal smoothing() const;
    void setSmoothing(qreal s);

    [[nodiscard]] QColor color() const;
    void setColor(const QColor& c);

    [[nodiscard]] bool cornerFill() const;
    void setCornerFill(bool e);
    QColor shadowColor() const { return m_shadowColor; }
    qreal shadowSize() const { return m_shadowSize; }
    qreal shadowOffset() const { return m_shadowOffset; }
    void setShadowColor(const QColor& color);
    void setShadowSize(qreal size);
    void setShadowOffset(qreal offset);

    void addShape(BlobShape* shape);
    void removeShape(BlobShape* shape);

    void setInvertedRect(BlobInvertedRect* rect);
    void clearInvertedRect(BlobInvertedRect* rect);

    [[nodiscard]] const QList<BlobShape*>& shapes() const;
    [[nodiscard]] BlobInvertedRect* invertedRect() const;

    void markDirty();
    void markShapeDirty(BlobShape* source);
    void ensurePhysicsUpdated();

signals:
    void smoothingChanged();
    void colorChanged();
    void cornerFillChanged();
    void shadowChanged();

private:
    qreal m_smoothing = 32.0;
    QColor m_color{ 0x44, 0x88, 0xff };
    bool m_cornerFill = true;
    QColor m_shadowColor{ Qt::transparent };
    qreal m_shadowSize = 0;
    qreal m_shadowOffset = 0;
    QList<BlobShape*> m_shapes;
    BlobInvertedRect* m_invertedRect = nullptr;
    bool m_physicsUpdated = false;
};

} // namespace hyprstack::blobs
