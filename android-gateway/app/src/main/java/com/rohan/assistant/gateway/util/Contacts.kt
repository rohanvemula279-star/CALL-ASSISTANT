package com.rohan.assistant.gateway.util

import android.content.Context
import android.provider.ContactsContract
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

object Contacts {
    /**
     * Returns the contact name for [phoneNumber], or null if not found.
     * Requires READ_CONTACTS permission.
     */
    suspend fun lookupName(context: Context, phoneNumber: String): String? =
        withContext(Dispatchers.IO) {
            if (phoneNumber.isBlank() || phoneNumber == "unknown") return@withContext null
            val uri = ContactsContract.PhoneLookup.CONTENT_FILTER_URI.buildUpon()
                .appendPath(phoneNumber).build()
            val cursor = context.contentResolver.query(
                uri,
                arrayOf(ContactsContract.PhoneLookup.DISPLAY_NAME),
                null, null, null,
            ) ?: return@withContext null
            cursor.use {
                if (it.moveToFirst()) {
                    val idx = it.getColumnIndex(ContactsContract.PhoneLookup.DISPLAY_NAME)
                    if (idx >= 0) it.getString(idx) else null
                } else null
            }
        }
}
