"""
Stock market story generator — produces 1000 silly kid-themed news stories
across all F&P reading levels explaining why stock prices go up or down.

Stories are generated combinatorially from templates per reading level band,
then seeded into the stock_stories table on first run.
"""

import random

# ---------- story templates by reading level band ----------
# Each band maps to a list of (headline_template, body_template) tuples.
# Placeholders: {name}, {emoji}, {symbol}, {reason}, {animal}, {food}, {number}, {color}, {place}

_ANIMALS = [
    "cat", "dog", "frog", "duck", "pig", "cow", "hen", "bug", "bat", "fox",
    "bear", "fish", "bird", "bee", "ant", "owl", "ram", "yak", "eel", "emu",
]

_FOODS = [
    "cake", "pie", "jam", "bread", "soup", "corn", "rice", "plum", "pear", "fig",
    "taco", "pizza", "cookie", "muffin", "waffle", "donut", "pretzel", "noodle",
    "pancake", "brownie",
]

_COLORS = [
    "red", "blue", "pink", "gold", "green", "purple", "orange", "yellow",
    "silver", "teal",
]

_PLACES = [
    "the park", "the moon", "the zoo", "the beach", "the lake", "the farm",
    "a castle", "a cave", "the jungle", "a cloud city", "an island",
    "a volcano", "the North Pole", "a treehouse", "the ocean floor",
]

_NUMBERS = [2, 3, 5, 7, 10, 12, 15, 20, 50, 100]

# ---- Level A-B (emergent, 1-2 sentences, sight words only) ----
_AB_UP = [
    ("{emoji} {name} is up!", "I see {name} go up. It is fun."),
    ("{emoji} {name} is big!", "I like {name}. It can go up."),
    ("{emoji} Go {name}!", "I see it go up. We like {name}."),
    ("{emoji} {name} is happy!", "{name} is up. I am happy."),
    ("{emoji} Up up up!", "{name} can go up. I see it go!"),
    ("{emoji} Yes {name}!", "It is up! I like {name} a lot."),
    ("{emoji} {name} wins!", "We see {name} go up. It is good."),
    ("{emoji} Look at {name}!", "I see {name}. It is up today."),
]

_AB_DOWN = [
    ("{emoji} {name} is down.", "I see {name} go down. It is sad."),
    ("{emoji} Oh no {name}!", "{name} is down. I am sad."),
    ("{emoji} {name} went down.", "I see it go down. We can see it."),
    ("{emoji} Down it goes!", "{name} is down today. It is not up."),
    ("{emoji} Not up today.", "I see {name}. It is down. Oh no."),
    ("{emoji} {name} is low.", "{name} went down. I can see it go."),
]

# ---- Level C-D (CVC + sight words, 2-3 sentences) ----
_CD_UP = [
    ("{emoji} {name} pops up!", "A {animal} got a big {food}. Now {name} is up! Kids are glad."),
    ("{emoji} {name} has a big day!", "A {color} {animal} ran to {name}. The stock went up. It is fun!"),
    ("{emoji} {name} did it!", "{name} had a {color} {food} sale. It sold a lot. The stock is up!"),
    ("{emoji} {name} jumps up!", "A {animal} at {name} had a big win. The stock got hot!"),
    ("{emoji} Good job {name}!", "{number} kids got {food} from {name}. Now the stock is up!"),
    ("{emoji} Wow {name}!", "A {animal} sat on a {color} box at {name}. Sales went up!"),
]

_CD_DOWN = [
    ("{emoji} {name} drops!", "A {animal} ate all the {food}. Now {name} is down. Oh no!"),
    ("{emoji} {name} has a bad day.", "The {color} {food} from {name} was bad. The stock fell down."),
    ("{emoji} {name} slips!", "A {animal} ran away with all the {food}. {name} went down!"),
    ("{emoji} Uh oh {name}!", "The {animal} at {name} was sad. Not a lot sold. Stock is down."),
    ("{emoji} {name} went down.", "{name} had a big {food} mess. {number} kids did not like it."),
    ("{emoji} Bad luck {name}!", "A {color} {animal} knocked over the {food}. {name} is down!"),
]

# ---- Level E-F (expanding vocab, 3-4 sentences) ----
_EF_UP = [
    ("{emoji} {name} soars higher!", "Today {name} went way up! A {color} {animal} found {number} boxes of {food} at {place}. Everyone wanted some. The stock jumped up fast!"),
    ("{emoji} Big news for {name}!", "{name} just made a new {color} {food} that tastes amazing. Kids at {place} lined up to buy it. The stock price went up a lot today!"),
    ("{emoji} {name} is on fire!", "A funny {animal} at {name} learned a new trick. It made {number} people laugh. Now everyone wants to buy {name} stock!"),
    ("{emoji} {name} hits a home run!", "Workers at {name} made {number} extra {food} today. A {animal} helped deliver them to {place}. The stock is going up!"),
    ("{emoji} Party at {name}!", "{name} threw a big {color} party at {place}. There was {food} for everyone. The stock price jumped after that!"),
]

_EF_DOWN = [
    ("{emoji} {name} takes a tumble!", "Oh no! A {animal} at {name} spilled {number} buckets of {food}. What a mess at {place}! The stock went down today."),
    ("{emoji} Not great for {name}.", "{name} tried to make {color} {food} but it tasted like a {animal}. Nobody wanted it. The stock dropped down."),
    ("{emoji} Oops at {name}!", "A {animal} broke the {color} machine at {name}. They couldn't make any {food}. The stock went down a lot!"),
    ("{emoji} {name} in trouble!", "Only {number} people came to {name} at {place} today. The {food} was cold. The stock price fell."),
    ("{emoji} Rough day for {name}.", "The {color} {animal} at {name} ate all the {food} again. There was nothing left to sell!"),
]

# ---- Level G-H (transitional, 4-5 sentences) ----
_GH_UP = [
    ("{emoji} {name} breaks records!", "{name} just had its best week ever! They sold {number} tons of {food} at {place}. A {color} {animal} was the company mascot and everyone loved it. Parents are buying the stock too. What a great time for {name}!"),
    ("{emoji} {name} launches something new!", "Big day for {name}! They invented a {color} {food} that makes you dance. A {animal} tested it first at {place}. Now {number} stores want to sell it. The stock price jumped way up!"),
    ("{emoji} Everyone loves {name}!", "A famous {animal} said that {name} is the best company ever. Kids at {place} agreed. They bought {number} {food} in one day. The stock is climbing higher and higher!"),
    ("{emoji} {name} expands!", "{name} opened a new store at {place} today. They hired {number} {animal}s to help run it. The {color} building looks amazing. Investors are excited and the stock went up!"),
]

_GH_DOWN = [
    ("{emoji} {name} hits a rough patch!", "{name} had a terrible day. Their {color} factory at {place} broke down. A {animal} accidentally pressed the wrong button. {number} orders of {food} were ruined. The stock dropped fast!"),
    ("{emoji} Bad news for {name}.", "Nobody came to the {name} store at {place} today. The {food} was too {color} and weird. A {animal} tried it and made a funny face. The stock went down again."),
    ("{emoji} {name} faces problems!", "A big storm hit {place} where {name} does business. The {color} roof flew off. {number} boxes of {food} got soaked. It will take a while to fix everything."),
    ("{emoji} Yikes for {name}!", "The {animal} who runs {name} accidentally ordered {number} wrong things. Instead of {food}, they got {color} socks. Customers were confused and the stock fell."),
]

# ---- Level I-J (fluent, 5-7 sentences) ----
_IJ_UP = [
    ("{emoji} {name} stock surges on big announcement!", "{name} surprised everyone today with an incredible new invention. They created a {color} {food} that actually glows in the dark! Scientists at {place} tested it and said it was perfectly safe to eat. A famous {animal} tasted it on live TV and did a happy dance. Orders are flooding in from {number} different countries. The stock price jumped by a huge amount. Investors couldn't be happier with {name} right now!"),
    ("{emoji} {name} wins big award!", "The World {food} Council just gave {name} its highest honor today. Their new {color} recipe beat out {number} other companies at {place}. A panel of {animal}s served as the judges and they loved every bite. The award comes with a giant golden trophy. Sales are expected to double next month. The stock price shot up right after the announcement!"),
    ("{emoji} {name} partners with famous company!", "{name} just announced a huge partnership today. They will be working with a team of {number} {animal}s at {place}. Together they plan to create the world's first {color} {food} theme park. The park will have rides, games, and all-you-can-eat {food}. Ticket pre-sales already broke records. This is the biggest deal in {name}'s history and the stock reflected it!"),
]

_IJ_DOWN = [
    ("{emoji} {name} stock sinks after recall!", "Bad news hit {name} hard today. They had to recall {number} boxes of their popular {color} {food}. It turns out a {animal} at {place} discovered they taste like old socks. Customers are asking for their money back. The company said they're working on fixing the recipe. But for now, the stock price dropped sharply. It might take a while to recover."),
    ("{emoji} Competitor steals {name}'s customers!", "A new rival company just opened right next to {name} at {place}. They sell {color} {food} for half the price. Already {number} customers have switched. Even the {animal} mascot looked sad about it. The {name} CEO said they have a plan to fight back. But investors aren't convinced yet and the stock fell."),
    ("{emoji} {name} factory flooded with {food}!", "Disaster at {name}! A pipe burst at their factory in {place} today. {number} gallons of {color} {food} mix flooded the building. A {animal} tried to swim through it but gave up. Production will be stopped for at least a week. The cleanup is going to cost a fortune. The stock dropped on the bad news."),
]

# ---- Level K-L (literary language, 6-8 sentences) ----
_KL_UP = [
    ("{emoji} {name} announces record-breaking quarter!", "{name} just released their earnings report, and it's spectacular. Revenue grew by {number} percent compared to last quarter. Their flagship {color} {food} product has become a sensation at {place}. A beloved {animal} celebrity endorsed the brand, sending social media into a frenzy. The company also announced plans to hire {number} new employees. Their innovative approach to business continues to impress analysts. Consumer satisfaction ratings are at an all-time high. The stock surged on the phenomenal results!"),
    ("{emoji} {name} makes groundbreaking discovery!", "Scientists at {name} made an astonishing discovery today at their lab in {place}. They found that mixing {color} sparkles with {food} creates something extraordinary. Initial tests showed that a {animal} who tried it could jump {number} times higher than normal. The discovery could revolutionize the entire industry. Patents have already been filed in {number} countries. Competitors are scrambling to catch up. This breakthrough sent the stock price soaring to new heights!"),
]

_KL_DOWN = [
    ("{emoji} {name} struggles with supply chain woes!", "{name} is facing serious challenges this week. A shortage of {color} {food} ingredients has disrupted production at {place}. Deliveries are delayed by {number} days on average. The {animal} drivers who transport goods are threatening to strike. Customer complaints have tripled since last month. The CEO addressed shareholders but couldn't provide a clear timeline for recovery. Analysts downgraded the stock. It was one of {name}'s worst trading days this year."),
    ("{emoji} {name} product launch goes horribly wrong!", "{name}'s highly anticipated new {color} {food} launched today — and it was a disaster. At the unveiling ceremony at {place}, a {animal} taste-tester immediately spit it out on live TV. The audience of {number} gasped in shock. Reviews called it 'the worst flavor experiment in history.' Social media exploded with funny memes about the failed product. The company's stock plummeted within hours. {name} promised to go back to the drawing board."),
]

# ---- Level M-P (independent/advanced, 8-12 sentences) ----
_MP_UP = [
    ("{emoji} {name} revolutionizes industry with bold move!", "{name} stunned the business world today with a revolutionary announcement that nobody saw coming. The company has developed a completely new type of {color} {food} using technology that was previously thought impossible. Testing at their facility in {place} showed remarkable results — {number} out of {number} participants gave it a perfect score. A distinguished {animal} professor from the University of Snack Sciences called it 'a paradigm shift.' The innovation uses half the resources of traditional methods, making it both cheaper and better for the environment. Pre-orders have already surpassed anything the company has seen before. Industry experts predict this could double {name}'s market share within a year. The stock rocketed upward as investors rushed to get in on the action. This could be the beginning of a whole new era for {name}!"),
]

_MP_DOWN = [
    ("{emoji} {name} faces investigation after complaints surge!", "Trouble is mounting for {name} after regulators at {place} announced a formal investigation into the company's practices. The probe was triggered by {number} customer complaints about their {color} {food} product. A prominent {animal} food critic published a devastating review, calling it 'an insult to taste buds everywhere.' Internal documents suggest the company knew about quality issues for months but chose to ignore them. Several key executives have already resigned. The company's reputation, once considered sterling, is now in serious jeopardy. Analysts have slashed their price targets across the board. The stock tumbled as investors headed for the exits. Recovery will require significant changes at every level of the organization."),
]

# ---- Level Q-T (advanced/proficient, 12-18 sentences) ----
_QT_UP = [
    ("{emoji} {name} leads market rally with transformative strategy!", "In what analysts are calling the most impressive corporate turnaround in recent memory, {name} has completely reinvented itself. The company unveiled a comprehensive new strategy at a packed investor conference in {place} yesterday. Central to the plan is their revolutionary {color} {food} technology, which uses artificial intelligence to customize flavors for individual customers. Early trials with {number} test subjects showed a 98% satisfaction rate — unprecedented in the industry. A renowned {animal} economist praised the approach, stating that {name} has 'cracked the code on consumer preferences.' The company also announced strategic partnerships with {number} major retailers, ensuring widespread distribution. Their sustainability initiative has earned praise from environmental groups, adding to the positive sentiment. Revenue projections for next quarter have been revised upward by {number} percent. The board of directors approved an ambitious expansion plan that includes new facilities at {place}. Employee morale is reportedly at an all-time high following generous bonus announcements. The stock has been climbing steadily all week and showed no signs of slowing down. Market observers believe {name} could become the dominant player in its sector within two years."),
]

_QT_DOWN = [
    ("{emoji} {name} plunges amid mounting crises!", "It has been an absolutely brutal week for {name}, as the company faces challenges on multiple fronts simultaneously. The crisis began when their flagship {color} {food} product was found to contain an ingredient that makes {animal}s sneeze uncontrollably. Regulators at {place} immediately issued a temporary sales ban, affecting {number} stores nationwide. The recall alone is estimated to cost the company millions. Making matters worse, a key patent expired this week, allowing competitors to legally copy their most profitable product. Internal surveys revealed that employee satisfaction has plummeted, with {number} percent of senior staff reportedly updating their resumes. The company's chief scientist resigned unexpectedly, citing 'irreconcilable differences' with management's direction. Social media campaigns calling for a boycott have gained significant traction, with {number} people signing an online petition. The CEO attempted to reassure investors during an emergency conference call, but stumbled through answers and failed to provide concrete solutions. Credit rating agencies are reviewing {name}'s debt status, which could make borrowing more expensive. The stock has lost value every single trading day this week. Analysts warn that without dramatic action, things could get even worse before they get better."),
]

# ---- Level U-Z2 (proficient-expert, 18-40 sentences) ----
_UZ_UP = [
    ("{emoji} {name} orchestrates masterful expansion that redefines market expectations!", """In a development that has sent shockwaves through the financial world, {name} has executed what industry insiders are calling the most brilliant strategic maneuver in a generation. The company, long known for its innovative {color} {food} products, announced a comprehensive expansion plan that touches every aspect of its business operations.

At a standing-room-only press conference in {place}, the CEO presented a vision so compelling that even skeptical analysts found themselves nodding in agreement. The centerpiece is a revolutionary new production method developed by a team of {number} scientists, led by a brilliant {animal} researcher who previously worked at the top laboratories in the world.

The new technology allows {name} to produce their signature {color} {food} at three times the speed and half the cost. Quality testing conducted independently at {place} confirmed that the product is not only cheaper to make but actually tastes significantly better. Consumer focus groups gave it the highest ratings ever recorded in the industry's history.

The expansion includes {number} new manufacturing facilities strategically located around the globe. Each facility will employ cutting-edge automation while still creating thousands of new jobs. Environmental impact assessments show the new process produces {number} percent less waste than traditional methods, earning praise from sustainability advocates.

Perhaps most impressively, {name} has secured exclusive distribution agreements with every major retailer. The stock price reflected the market's enthusiasm, climbing throughout the day on volume that shattered previous records. Long-term investors are particularly excited about the company's five-year roadmap, which promises continued innovation and growth."""),
]

_UZ_DOWN = [
    ("{emoji} {name} faces perfect storm of challenges as stock enters freefall!", """In what is rapidly becoming one of the most dramatic corporate downfalls in recent history, {name} is grappling with an extraordinary confluence of problems that have sent its stock into a steep decline.

The troubles began when investigative journalists at {place} uncovered that the company's celebrated {color} {food} product had been manufactured using outdated equipment. The report, which included testimony from {number} former employees, painted a picture of systematic corner-cutting and neglect.

A prominent {animal} food safety expert appeared on national television to express serious concerns. Within hours, social media was flooded with customers sharing their own negative experiences. The hashtag moved to the top trending spot and stayed there for three consecutive days.

Regulators wasted no time in responding. Inspectors descended on {name}'s facilities at {place} and found {number} violations of industry standards. A temporary production halt was ordered, affecting supply chains that depend on the company's output.

The financial fallout has been severe. The company's credit rating was downgraded, making it more expensive to borrow money for operations. {number} institutional investors have reduced their positions. The board of directors called an emergency meeting, but no clear resolution emerged.

Competitors have wasted no time exploiting the situation, launching aggressive marketing campaigns targeting {name}'s disaffected customers. Industry analysts estimate that {name} could lose up to {number} percent of its market share if the crisis is not resolved within the next quarter. The road to recovery, if one exists, will be long and difficult."""),
]

# Map level bands to templates
_TEMPLATES = {
    "AB": {"up": _AB_UP, "down": _AB_DOWN},
    "CD": {"up": _CD_UP, "down": _CD_DOWN},
    "EF": {"up": _EF_UP, "down": _EF_DOWN},
    "GH": {"up": _GH_UP, "down": _GH_DOWN},
    "IJ": {"up": _IJ_UP, "down": _IJ_DOWN},
    "KL": {"up": _KL_UP, "down": _KL_DOWN},
    "MP": {"up": _MP_UP, "down": _MP_DOWN},
    "QT": {"up": _QT_UP, "down": _QT_DOWN},
    "UZ": {"up": _UZ_UP, "down": _UZ_DOWN},
}

_LEVEL_TO_BAND = {
    "A": "AB", "B": "AB",
    "C": "CD", "D": "CD",
    "E": "EF", "F": "EF",
    "G": "GH", "H": "GH",
    "I": "IJ", "J": "IJ",
    "K": "KL", "L": "KL",
    "M": "MP", "N": "MP", "O": "MP", "P": "MP",
    "Q": "QT", "R": "QT", "S": "QT", "T": "QT",
    "U": "UZ", "V": "UZ", "W": "UZ", "X": "UZ",
    "Y": "UZ", "Z": "UZ", "Z1": "UZ", "Z2": "UZ",
}


def _fill_template(template: str, stock_name: str, stock_emoji: str, stock_symbol: str, rng: random.Random) -> str:
    """Fill a template string with random silly values."""
    result = template.format(
        name=stock_name,
        emoji=stock_emoji,
        symbol=stock_symbol,
        animal=rng.choice(_ANIMALS),
        food=rng.choice(_FOODS),
        color=rng.choice(_COLORS),
        place=rng.choice(_PLACES),
        number=rng.choice(_NUMBERS),
    )
    # Fix double periods from names ending in "." (e.g. "Co.")
    return result.replace("..", ".").replace(".!", "!")


def generate_stories(stocks: list[tuple], target_count: int = 1000, seed: int = 42) -> list[dict]:
    """
    Generate `target_count` stock stories spread across stocks, levels, and directions.

    Args:
        stocks: list of (id, symbol, name, emoji) tuples
        target_count: how many stories to generate
        seed: random seed for reproducibility

    Returns:
        list of dicts with keys: stock_id, fp_level, direction, headline, body
    """
    rng = random.Random(seed)
    all_levels = list(_LEVEL_TO_BAND.keys())
    stories = []

    # Round-robin through stocks, levels, and directions to get even coverage
    idx = 0
    attempts = 0
    max_attempts = target_count * 10  # safety valve

    while len(stories) < target_count and attempts < max_attempts:
        attempts += 1
        stock_id, symbol, name, emoji = stocks[idx % len(stocks)]
        level = all_levels[idx % len(all_levels)]
        direction = "up" if (idx // len(all_levels)) % 2 == 0 else "down"

        band = _LEVEL_TO_BAND[level]
        templates = _TEMPLATES[band][direction]
        headline_tpl, body_tpl = rng.choice(templates)

        headline = _fill_template(headline_tpl, name, emoji, symbol, rng)
        body = _fill_template(body_tpl, name, emoji, symbol, rng)

        stories.append({
            "stock_id": stock_id,
            "fp_level": level,
            "direction": direction,
            "headline": headline,
            "body": body,
        })
        idx += 1

    return stories


async def seed_stock_stories(conn, stocks: list[tuple], target_count: int = 1000) -> int:
    """Seed stock stories into the database if none exist yet."""
    existing = await conn.fetchval("SELECT COUNT(*) FROM stock_stories")
    if existing > 0:
        return existing

    stories = generate_stories(stocks, target_count)

    for s in stories:
        await conn.execute(
            """INSERT INTO stock_stories (stock_id, fp_level, direction, headline, body)
               VALUES ($1, $2, $3, $4, $5)""",
            s["stock_id"], s["fp_level"], s["direction"], s["headline"], s["body"],
        )

    return len(stories)
