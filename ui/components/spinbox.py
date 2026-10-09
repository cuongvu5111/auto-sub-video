"""
AutoDub Studio - RobustSpinBox Component.
Custom QSpinBox that gracefully extracts integers ignoring trailing suffixes (e.g. ' px').
"""

import re
from PySide6.QtGui import QValidator
from PySide6.QtWidgets import QSpinBox


class RobustSpinBox(QSpinBox):
    """
    QSpinBox thông minh tự động bóc tách số và bỏ qua hậu tố ' px' hoặc nhập thiếu khoảng trắng,
    tránh việc reset về giá trị mặc định khi người dùng gõ rồi click ra ngoài (focus loss).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setKeyboardTracking(False)
        self.lineEdit().editingFinished.connect(self._on_editing_finished)

    def _on_editing_finished(self):
        self.interpretText()

    def valueFromText(self, text: str) -> int:
        nums = re.findall(r"\d+", text)
        if nums:
            val = int(nums[0])
            return max(self.minimum(), min(self.maximum(), val))
        return self.value()

    def validate(self, text: str, pos: int):
        return (QValidator.State.Acceptable, text, pos)
