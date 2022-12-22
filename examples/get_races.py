import os
from betwatch import BetwatchClient
from dotenv import load_dotenv


def main():
    api_key = os.getenv("API_KEY")
    if not api_key:
        raise Exception("API_KEY not set in .env file")

    client = BetwatchClient(api_key=api_key)
    races = client.get_races("2022-12-21", "2022-12-22")
    if races:
        next_open = next((r for r in races if r.is_open() and r.id), None)
        if next_open and next_open.id:
            race = client.get_race(next_open.id)
            if race and race.meeting:
                print(f"Received race data for {race.meeting.track} R{race.number}")


if __name__ == "__main__":
    load_dotenv()
    main()
