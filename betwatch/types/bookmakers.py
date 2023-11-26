from enum import Enum


class Bookmaker(str, Enum):
    TAB = "Tab"
    SPORTSBET = "Sportsbet"
    POINTSBET = "Pointsbet"
    UNIBET = "Unibet"
    NEDS = "Neds"
    LADBROKES = "Ladbrokes"
    BOOKMAKER = "Bookmaker"
    TABTOUCH = "Tabtouch"
    PALMERBET = "Palmerbet"
    DABBLE = "Dabble"
    MONEYBALL = "Moneyball"
    BLUEBET = "Bluebet"
    BETRIGHT = "Betright"
    BETFLUX = "Betflux"
    MINTBET = "Mintbet"
    BAGGYBET = "Baggybet"
    BETDELUXE = "Betdeluxe"
    WINBET = "Winbet"
    TEXBET = "Texbet"
    REALBOOKIE = "Realbookie"
    PICNICBET = "Picnicbet"
    CROSSBET = "Crossbet"
    ZBET = "Zbet"
    WISHBET = "Wishbet"
    PUNT123 = "Punt123"
    MARANTELLIBET = "Marantellibet"
    GETSETBET = "Getsetbet"
    OKEBET = "Okebet"
    READYBET = "Readybet"
    BETGOLD = "Betgold"
    BOSSBET = "Bossbet"
    RAMBET = "Rambet"
    ROBWATERHOUSE = "Robwaterhouse"
    SWIFTBET = "Swiftbet"
    BETNATION = "Betnation"
    UPCOZ = "Upcoz"
    BETR = "Betr"
    FOXCATCHER = "Foxcatcher"
    PLAYUP = "Playup"
    BOOKI = "Booki"
    COLOSSALBET = "Colossalbet"
    BOOMBET = "Boombet"
    TOPSPORT = "Topsport"
    SOUTHERNCROSSBET = "Southerncrossbet"
    ELITEBET = "Elitebet"
    WINNERSBET = "Winnersbet"
    JIMMYBET = "Jimmybet"
    BETBARN = "Betbarn"
    ACTIONBET = "Actionbet"
    BBET = "Bbet"
    WEBETNET = "Webetnet"
    BETHUNTER = "Bethunter"
    GOLDBET = "Goldbet"
    MIDASBET = "Midasbet"
    VICBET = "Vicbet"
    BETDECK = "Betdeck"
    BETBETBET = "BetBetBet"
    PUNTERSPAL = "PuntersPal"
    LYNCHBET = "Lynchbet"
    LUCASBET = "Lucasbet"
    PENDLEBURYBET = "Pendleburybet"
    TOMBET = "Tombet"
    TRACKBET = "Trackbet"
    WOODCOCKRACING = "Woodcockracing"
    VIPBETTINGSERVICES = "Vipbettingservices"
    DAVEBET = "Davebet"
    GALLOPBET = "Gallopbet"
    RIVERBET = "Riverbet"
    BARRINGTONBOOKMAKING = "Barringtonbookmaking"
    BUSHBET = "Bushbet"
    TOPODDS = "Topodds"
    BEAZABET = "Beazabet"
    PUNTONDOGS = "PuntOnDogs"
    PICKLEBET = "Picklebet"
    BETGALAXY = "Betgalaxy"
    DIAMONDBET = "Diamondbet"
    BITWINNING = "Bitwinning"
    COMBET = "Combet"
    BETM = "BetM"
    ULTRABET = "Ultrabet"
    THUNDERBET = "Thunderbet"
    ESKANDERBET = "EskanderBet"
    SPORTCHAMPS = "SportChamps"
    SURGE = "Surge"
    BETESTATE = "Betestate"
    CHASEBET = "Chasebet"
    BET66 = "Bet66"
    BOOKIEPRICE = "BookiePrice"

    def __str__(self):
        return self.value

    def __repr__(self):
        return self.value

    def __eq__(self, other):
        if isinstance(other, Bookmaker):
            return self.value == other.value
        elif isinstance(other, str):
            return self.value == other
        else:
            return False

    def __hash__(self):
        return hash(self.value)
