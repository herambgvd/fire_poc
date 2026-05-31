from PyQt6.QtCore import Qt, QParallelAnimationGroup, QPropertyAnimation, QAbstractAnimation
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QToolButton,
                             QScrollArea, QSizePolicy, QFrame)

class CollapsiblePanel(QWidget):
    def __init__(self, title="", animationDuration=200, parent=None):
        super().__init__(parent)

        self.animationDuration = animationDuration
        self.toggleAnimation = QParallelAnimationGroup(self)
        
        self.toggleButton = QToolButton(self)
        self.toggleButton.setStyleSheet("QToolButton { border: none; font-weight: bold; font-size: 14px; text-align: left; }")
        self.toggleButton.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggleButton.setArrowType(Qt.ArrowType.RightArrow)
        self.toggleButton.setText(" " + title)
        self.toggleButton.setCheckable(True)
        self.toggleButton.setChecked(False)

        # Header Line
        headerLine = QFrame()
        headerLine.setFrameShape(QFrame.Shape.HLine)
        headerLine.setFrameShadow(QFrame.Shadow.Sunken)
        headerLine.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        self.contentArea = QScrollArea(self)
        self.contentArea.setStyleSheet("QScrollArea { border: none; }")
        self.contentArea.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        # start out collapsed
        self.contentArea.setMaximumHeight(0)
        self.contentArea.setMinimumHeight(0)
        
        # Animations
        self.contentAnimation = QPropertyAnimation(self.contentArea, b"maximumHeight")
        self.contentAnimation.setDuration(self.animationDuration)
        self.toggleAnimation.addAnimation(self.contentAnimation)
        
        mainLayout = QVBoxLayout(self)
        mainLayout.setSpacing(0)
        mainLayout.setContentsMargins(0, 0, 0, 0)
        
        headerLayout = QHBoxLayout()
        headerLayout.addWidget(self.toggleButton)
        headerLayout.addWidget(headerLine)
        
        mainLayout.addLayout(headerLayout)
        mainLayout.addWidget(self.contentArea)
        
        self.toggleButton.clicked.connect(self.on_pressed)

    def setContentLayout(self, layout):
        old_layout = self.contentArea.layout()
        if old_layout:
            QWidget().setLayout(old_layout)
        
        content = QWidget()
        content.setLayout(layout)
        self.contentArea.setWidget(content)
        self.contentArea.setWidgetResizable(True)
        
        # Update animation heights based on the layout's size hint
        collapsedHeight = 0
        contentHeight = layout.sizeHint().height() + 10
        self.contentAnimation.setStartValue(collapsedHeight)
        self.contentAnimation.setEndValue(contentHeight)
        
        # start open by default
        self.toggleButton.setChecked(True)
        self.contentArea.setMaximumHeight(contentHeight)
        self.toggleButton.setArrowType(Qt.ArrowType.DownArrow)

    def on_pressed(self):
        checked = self.toggleButton.isChecked()
        self.toggleButton.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
        self.toggleAnimation.setDirection(QAbstractAnimation.Direction.Forward if checked else QAbstractAnimation.Direction.Backward)
        self.toggleAnimation.start()
