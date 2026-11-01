"""
Modern Dark Theme Styling for OpenClip.
Features deep charcoal palette, emerald/indigo accents, crisp typography, and sleek widgets.
"""

DARK_THEME_QSS = """
/* Global Window & Fonts */
QWidget {
    background-color: #111216;
    color: #E2E8F0;
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, "Roboto", sans-serif;
    font-size: 13px;
    selection-background-color: #3B82F6;
    selection-color: #FFFFFF;
}

/* Card Containers & Panels */
QFrame#card {
    background-color: #1A1C23;
    border: 1px solid #282C37;
    border-radius: 10px;
    padding: 12px;
}

QFrame#sidebar {
    background-color: #16181F;
    border-right: 1px solid #252834;
}

QFrame#header {
    background-color: #14161C;
    border-bottom: 1px solid #232733;
}

/* Tabs */
QTabWidget::pane {
    border: 1px solid #282C37;
    background-color: #181A22;
    border-radius: 8px;
    top: -1px;
}

QTabBar::tab {
    background-color: #14161C;
    color: #94A3B8;
    padding: 10px 22px;
    margin-right: 4px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    font-weight: 600;
}

QTabBar::tab:selected {
    background-color: #1E222D;
    color: #38BDF8;
    border-bottom: 2px solid #38BDF8;
}

QTabBar::tab:hover:!selected {
    background-color: #1A1D27;
    color: #CBD5E1;
}

/* Push Buttons */
QPushButton {
    background-color: #272B38;
    color: #F8FAFC;
    border: 1px solid #3B4254;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #32384A;
    border-color: #4B5563;
}

QPushButton:pressed {
    background-color: #1F232F;
}

QPushButton:disabled {
    background-color: #1B1D25;
    color: #64748B;
    border-color: #232733;
}

/* Primary Action Button (Gradient Accent) */
QPushButton#primaryButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563EB, stop:1 #06B6D4);
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 12px 24px;
    font-size: 14px;
    font-weight: bold;
}

QPushButton#primaryButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1D4ED8, stop:1 #0891B2);
}

QPushButton#primaryButton:pressed {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1E40AF, stop:1 #0E7490);
}

/* Danger / Cancel Button */
QPushButton#dangerButton {
    background-color: #7F1D1D;
    color: #FECACA;
    border: 1px solid #991B1B;
    border-radius: 8px;
    padding: 12px 20px;
    font-size: 14px;
    font-weight: bold;
}

QPushButton#dangerButton:hover {
    background-color: #991B1B;
}

/* Line Edit & Inputs */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #14161E;
    color: #F1F5F9;
    border: 1px solid #2E3445;
    border-radius: 6px;
    padding: 8px 12px;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 1px solid #38BDF8;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 25px;
    border-left: 1px solid #2E3445;
}

QComboBox QAbstractItemView {
    background-color: #1A1D27;
    color: #F1F5F9;
    border: 1px solid #38BDF8;
    selection-background-color: #2563EB;
}

/* Sliders */
QSlider::groove:horizontal {
    border: none;
    height: 6px;
    background: #252A38;
    border-radius: 3px;
}

QSlider::sub-page:horizontal {
    background: #06B6D4;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #38BDF8;
    border: 2px solid #FFFFFF;
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
}

/* Progress Bar */
QProgressBar {
    background-color: #14161E;
    border: 1px solid #2E3445;
    border-radius: 6px;
    text-align: center;
    color: #FFFFFF;
    font-weight: 600;
    height: 20px;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3B82F6, stop:1 #10B981);
    border-radius: 5px;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background: #14161E;
    width: 8px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #2E3445;
    min-height: 20px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #475569;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* Badges & Labels */
QLabel#badgeOk {
    background-color: #064E3B;
    color: #6EE7B7;
    border: 1px solid #059669;
    border-radius: 4px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 600;
}

QLabel#badgeHw {
    background-color: #1E3A5F;
    color: #93C5FD;
    border: 1px solid #2563EB;
    border-radius: 4px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 600;
}

QLabel#titleLabel {
    font-size: 20px;
    font-weight: 800;
    color: #FFFFFF;
}

QLabel#subTitleLabel {
    font-size: 12px;
    color: #94A3B8;
}

/* List Widget */
QListWidget {
    background-color: #14161E;
    border: 1px solid #282C37;
    border-radius: 8px;
    padding: 6px;
}

QListWidget::item {
    background-color: #1A1D27;
    border: 1px solid #282C37;
    border-radius: 6px;
    padding: 10px;
    margin-bottom: 6px;
}

QListWidget::item:hover {
    background-color: #232735;
    border-color: #38BDF8;
}

QListWidget::item:selected {
    background-color: #1E3A8A;
    border: 1px solid #60A5FA;
}
"""
