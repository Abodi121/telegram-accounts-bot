#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import logging
import threading
import time
from datetime import datetime
from pathlib import Path

class UserDatabase:
    def __init__(self, db_file="users.json"):
        self.db_file = db_file
        self.users = self.load_database()
    
    def load_database(self):
        """تحميل قاعدة البيانات من الملف"""
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"خطأ في تحميل قاعدة البيانات: {e}")
                return {}
        return {}
    
    def save_database(self):
        """حفظ قاعدة البيانات في الملف"""
        try:
            with open(self.db_file, 'w', encoding='utf-8') as f:
                json.dump(self.users, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"خطأ في حفظ قاعدة البيانات: {e}")
            return False
    
    def get_user(self, user_id, give_welcome_credits=False):
        """الحصول على بيانات المستخدم"""
        user_id = str(user_id)
        is_new_user = user_id not in self.users

        if is_new_user:
            # إنشاء مستخدم جديد
            initial_credits = 100 if give_welcome_credits else 0
            self.users[user_id] = {
                "credits": initial_credits,
                "total_purchases": 0,
                "join_date": datetime.now().isoformat(),
                "last_activity": datetime.now().isoformat(),
                "username": "",
                "first_name": "",
                "is_banned": False,
                "is_new": True,  # علامة للمستخدم الجديد
                "welcome_credits_given": give_welcome_credits
            }
            self.save_database()

        # تحديث آخر نشاط
        self.users[user_id]["last_activity"] = datetime.now().isoformat()
        return self.users[user_id], is_new_user
    
    def update_user_info(self, user_id, username=None, first_name=None, give_welcome_credits=False):
        """تحديث معلومات المستخدم"""
        user_id = str(user_id)
        user, is_new = self.get_user(user_id, give_welcome_credits)

        if username:
            user["username"] = username
        if first_name:
            user["first_name"] = first_name

        # إزالة علامة المستخدم الجديد بعد التحديث الأول
        if "is_new" in user:
            user["is_new"] = False

        self.save_database()
        return is_new

    def get_credits(self, user_id):
        """الحصول على كريدت المستخدم"""
        user, _ = self.get_user(user_id)
        return user["credits"]
    
    def add_credits(self, user_id, amount):
        """إضافة كريدت للمستخدم"""
        user, _ = self.get_user(user_id)
        user["credits"] += amount
        self.save_database()
        return user["credits"]

    def deduct_credits(self, user_id, amount):
        """خصم كريدت من المستخدم"""
        user, _ = self.get_user(user_id)
        if user["credits"] >= amount:
            user["credits"] -= amount
            user["total_purchases"] += 1
            self.save_database()
            return True
        return False

    def set_credits(self, user_id, amount):
        """تعيين كريدت المستخدم"""
        user, _ = self.get_user(user_id)
        user["credits"] = amount
        self.save_database()
        return amount

    def ban_user(self, user_id):
        """حظر المستخدم"""
        user, _ = self.get_user(user_id)
        user["is_banned"] = True
        self.save_database()

    def unban_user(self, user_id):
        """إلغاء حظر المستخدم"""
        user, _ = self.get_user(user_id)
        user["is_banned"] = False
        self.save_database()

    def is_banned(self, user_id):
        """التحقق من حظر المستخدم"""
        user, _ = self.get_user(user_id)
        return user.get("is_banned", False)
    
    def get_all_users(self):
        """الحصول على جميع المستخدمين"""
        return self.users
    
    def get_user_count(self):
        """الحصول على عدد المستخدمين"""
        return len(self.users)
    
    def get_total_credits(self):
        """الحصول على إجمالي الكريدت"""
        return sum(user["credits"] for user in self.users.values())
    
    def get_stats(self):
        """الحصول على إحصائيات"""
        total_users = len(self.users)
        total_credits = sum(user["credits"] for user in self.users.values())
        total_purchases = sum(user["total_purchases"] for user in self.users.values())
        banned_users = sum(1 for user in self.users.values() if user.get("is_banned", False))
        
        return {
            "total_users": total_users,
            "total_credits": total_credits,
            "total_purchases": total_purchases,
            "banned_users": banned_users,
            "active_users": total_users - banned_users
        }
