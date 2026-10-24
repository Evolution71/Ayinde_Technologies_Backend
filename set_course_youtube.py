"""
Link a course to its YouTube tutorial, practical code and notes.

Examples (run from the backend folder):
    python set_course_youtube.py 3 --youtube-url https://youtu.be/abc123 --code-url https://github.com/... --notes-file notes_course3.txt --show
    python set_course_youtube.py 3 --hide

The notes file holds one bullet per line. Prices are not set here: the checkout
always uses the course price stored in the database.
"""

import argparse
import sys

from database import SessionLocal
from models import Course


def main():
    parser = argparse.ArgumentParser(description="Set YouTube fields on a course.")
    parser.add_argument("course_id", type=int)
    parser.add_argument("--youtube-url")
    parser.add_argument("--live-url")
    parser.add_argument("--code-url")
    parser.add_argument("--notes-file")
    visibility = parser.add_mutually_exclusive_group()
    visibility.add_argument("--show", action="store_true", help="show on the home page YouTube section")
    visibility.add_argument("--hide", action="store_true", help="hide from the YouTube section")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        course = db.query(Course).filter(Course.id == args.course_id).first()
        if not course:
            print(f"Course {args.course_id} not found.")
            return 1

        if args.youtube_url is not None:
            course.youtube_url = args.youtube_url or None
        if args.live_url is not None:
            course.youtube_live_url = args.live_url or None
        if args.code_url is not None:
            course.practical_code_url = args.code_url or None
        if args.notes_file:
            with open(args.notes_file, encoding="utf-8") as fh:
                course.course_notes = fh.read()
        if args.show:
            course.show_on_youtube = True
        if args.hide:
            course.show_on_youtube = False

        db.commit()
        print(f"Updated course {course.id} '{course.title}' | price {course.price} {course.currency} | "
              f"show_on_youtube={course.show_on_youtube}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
