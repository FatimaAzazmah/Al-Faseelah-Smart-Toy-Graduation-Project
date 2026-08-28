# -*- coding: utf-8 -*-
"""
add_police_content.py - adds a learn card for the 'police' piece.
Run once:  python3 add_police_content.py
Safe: checks the piece exists and skips if a card is already present.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from content_manager import sb

POLICE_CARD = {
    "vocab": [
        {"ar": "شرطي", "en": "police officer"},
        {"ar": "أمان", "en": "safety"},
        {"ar": "مساعدة", "en": "help"},
        {"ar": "قانون", "en": "law"},
        {"ar": "إشارة المرور", "en": "traffic light"},
        {"ar": "صافرة", "en": "whistle"},
    ],
    "values": [
        {"ar": "الشرطي صديقنا يحمينا ونثق به",
         "en": "The police officer is our friend who protects us and we trust"},
        {"ar": "نطلب المساعدة إذا ضعنا أو خفنا",
         "en": "We ask for help if we are lost or scared"},
        {"ar": "نحترم القانون ونتبع القواعد",
         "en": "We respect the law and follow the rules"},
    ],
    "facts_l1": [
        {"ar": "الشرطي يحمي الناس ويحافظ على الأمان",
         "en": "The police officer protects people and keeps everyone safe"},
        {"ar": "الشرطي ينظم حركة السيارات في الطريق",
         "en": "The police officer directs the cars on the road"},
        {"ar": "إذا ضاع الطفل يذهب للشرطي ليساعده",
         "en": "If a child is lost, they go to a police officer for help"},
    ],
    "facts_l2": [
        {"ar": "الشرطي يلبس زيا خاصا حتى نعرفه بسهولة",
         "en": "The police officer wears a special uniform so we recognize them easily"},
        {"ar": "الشرطي يستخدم الصافرة وإشارات يده لتنظيم السير",
         "en": "The officer uses a whistle and hand signals to direct traffic"},
        {"ar": "الشرطي يعمل نهارا وليلا ليبقى الجميع بأمان",
         "en": "Police work day and night to keep everyone safe"},
    ],
    "facts_l3": [
        {"ar": "للشرطة رقم هاتف خاص نتصل به وقت الخطر فقط",
         "en": "The police have a special phone number we call only in emergencies"},
        {"ar": "الشرطي يتعاون مع الإطفائي والإسعاف لمساعدة الناس",
         "en": "Police work together with firefighters and paramedics to help people"},
    ],
    "title_ar": "عن الشرطي",
    "title_en": "About the Police Officer",
    "play_ideas": [
        {"ar": "ماذا يفعل الشرطي عند إشارة المرور؟",
         "en": "What does the police officer do at the traffic light?"},
        {"ar": "لو ضعت في السوق، لمن تذهب؟",
         "en": "If you got lost in the market, who would you go to?"},
        {"ar": "لعبة حركية: قف مثل الشرطي وأشر للسيارات أن تقف",
         "en": "Movement game: stand like an officer and signal the cars to stop"},
    ],
    "did_you_know": [
        {"ar": "بعض رجال الشرطة عندهم كلاب مدربة تساعدهم في عملهم!",
         "en": "Some police officers have trained dogs that help them at work!"},
        {"ar": "الشرطي يتعلم كثيرا قبل أن يصير شرطيا ليحمينا جيدا",
         "en": "A police officer trains a lot before the job, to protect us well"},
    ],
    "open_questions": [
        {"ar": "لو كنت شرطيا، كيف ستساعد الناس؟",
         "en": "If you were a police officer, how would you help people?"},
        {"ar": "لماذا برأيك من المهم أن نتبع قواعد الطريق؟",
         "en": "Why do you think it is important to follow road rules?"},
    ],
}


def main():
    # 1) find the police piece
    p = sb.table("pieces").select("id,zone_id,key,name_ar").eq("key", "police").execute()
    if not p.data:
        print("[!] No 'police' piece found in DB. Nothing to do.")
        return
    piece = p.data[0]
    print(f"[i] police piece: id={piece['id']} zone_id={piece['zone_id']} name={piece['name_ar']}")

    # 2) skip if a learn card already exists for this piece
    existing = sb.table("content").select("id") \
        .eq("piece_id", piece["id"]).eq("type", "learn").execute()
    if existing.data:
        print(f"[i] police already has {len(existing.data)} learn card(s). Skipping insert.")
        return

    # 3) insert
    row = {
        "zone_id":        piece["zone_id"],
        "piece_id":       piece["id"],
        "type":           "learn",
        "difficulty":     1,
        "knowledge_card": POLICE_CARD,
        "trackable_key":  None,
        "is_active":      True,
    }
    r = sb.table("content").insert(row).execute()
    if r.data:
        print(f"[✓] Inserted police learn card | content id={r.data[0].get('id')}")
    else:
        print(f"[!] Insert returned no data: {r}")


if __name__ == "__main__":
    main()
