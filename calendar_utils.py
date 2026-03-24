from korean_lunar_calendar import KoreanLunarCalendar

class CalendarUtils:
    def __init__(self):
        self.lunar_cal = KoreanLunarCalendar()

    def get_lunar_date(self, year, month, day):
        self.lunar_cal.setSolarDate(year, month, day)
        return f"{self.lunar_cal.lunarMonth}.{self.lunar_cal.lunarDay}"

    def get_solar_term(self, year, month, day):
        if year < 2000 or year > 2099: return ""
        y = year - 2000
        constants = {
            1: [("소한", 5.4055), ("대한", 20.12)], 2: [("입춘", 4.6295), ("우수", 19.204)],
            3: [("경칩", 5.6254), ("춘분", 20.646)], 4: [("청명", 4.908), ("곡우", 20.1)],
            5: [("입하", 5.52), ("소만", 21.04)], 6: [("망종", 5.678), ("하지", 21.37)],
            7: [("소서", 7.108), ("대서", 22.83)], 8: [("입추", 7.446), ("처서", 23.25)],
            9: [("백로", 7.646), ("추분", 23.042)], 10: [("한로", 8.318), ("상강", 23.438)],
            11: [("입동", 7.438), ("소설", 22.36)], 12: [("대설", 7.18), ("동지", 21.94)]
        }
        for name, const in constants.get(month, []):
            term_day = int(const + 0.2422 * y - int((y - 1) / 4))
            if day == term_day: return name
        return ""

    @staticmethod
    def is_red_holiday(summary):
        not_red_kw = ["어버이날", "스승의날", "제헌절", "식목일", "국군의 날", "대보름", "단오", "유두", "칠석", "동지", "노동절", "근로자의 날", "발렌타인데이", "화이트데이"]
        return not any(kw in summary for kw in not_red_kw)
