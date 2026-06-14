package com.rohan.assistant.gateway.service

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Path
import android.graphics.Rect
import android.os.Build
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import com.rohan.assistant.gateway.util.Logger

class CallAnswerAccessibilityService : AccessibilityService() {

    private var callHandled = false

    override fun onAccessibilityEvent(event: AccessibilityEvent) {
        if (callHandled) return

        val packageName = event.packageName?.toString() ?: return
        if (packageName != "com.android.incallui" &&
            packageName != "com.android.dialer" &&
            packageName != "com.google.android.dialer" &&
            !packageName.contains("incall") &&
            !packageName.contains("phone")
        ) return

        when (event.eventType) {
            AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED,
            AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED -> {
                findAndClickAnswerButton()
            }
        }
    }

    private fun findAndClickAnswerButton() {
        val root = rootInActiveWindow ?: return
        try {
            val answerButton = findAnswerButton(root)
            if (answerButton != null) {
                Logger.i(TAG, "Found answer button, clicking...")
                clickButton(answerButton)
                callHandled = true
            }
        } finally {
            root.recycle()
        }
    }

    private fun findAnswerButton(node: AccessibilityNodeInfo): AccessibilityNodeInfo? {
        if (isAnswerButton(node)) return node
        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            val found = findAnswerButton(child)
            if (found != null) return found
        }
        return null
    }

    private fun isAnswerButton(node: AccessibilityNodeInfo): Boolean {
        val desc = node.contentDescription?.toString()?.lowercase() ?: ""
        val id = node.viewIdResourceName?.lowercase() ?: ""
        val cls = node.className?.toString()?.lowercase() ?: ""

        val matchDesc = desc.contains("answer") || desc.contains("accept") ||
            desc.contains("pick up") || desc.contains("swipe to answer")
        val matchId = id.contains("answer") || id.contains("btn_answer") ||
            id.contains("incall_answer") || id.contains("answer_button")
        val matchCls = cls.contains("button") || cls.contains("imagebutton")

        val clickable = node.isClickable && node.isVisibleToUser
        return clickable && (matchDesc || matchId) && node.isEnabled
    }

    private fun clickButton(node: AccessibilityNodeInfo) {
        val bounds = Rect()
        node.getBoundsInScreen(bounds)

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
            val centerX = bounds.centerX().toFloat()
            val centerY = bounds.centerY().toFloat()
            val path = Path().apply { moveTo(centerX, centerY) }
            val gesture = GestureDescription.Builder()
                .addStroke(GestureDescription.StrokeDescription(path, 0, 100))
                .build()
            dispatchGesture(gesture, null, null)
            Logger.i(TAG, "Dispatched click gesture at ($centerX, $centerY)")
        } else {
            node.performAction(AccessibilityNodeInfo.ACTION_CLICK)
            Logger.i(TAG, "Performed ACTION_CLICK on answer button")
        }
    }

    fun resetCallHandled() {
        callHandled = false
    }

    override fun onInterrupt() {
        Logger.i(TAG, "Accessibility service interrupted")
    }

    companion object {
        private const val TAG = "CallAnswerService"
    }
}
