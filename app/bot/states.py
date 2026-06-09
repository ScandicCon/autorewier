from aiogram.fsm.state import State, StatesGroup


class NewCheck(StatesGroup):
    url = State()
    preferences = State()
    manual = State()
    brand = State()
    model = State()
    year = State()
    mileage = State()
    price = State()
    engine = State()
    transmission = State()
    defects = State()
    reseller = State()
    target_price = State()


class PostCheck(StatesGroup):
    pick_inspection = State()
    defects = State()
    notes = State()
