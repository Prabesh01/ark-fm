word_lists = {
    'adjective': [
        'happy', 'mysterious', 'quick', 'silent', 'brave', 'clever', 'ancient', 'modern',
        'digital', 'virtual', 'cosmic', 'stellar', 'lunar', 'solar', 'electric', 'atomic',
        'quantum', 'neural', 'cyber', 'phantom', 'shadow', 'crimson', 'azure', 'emerald',
        'golden', 'silver', 'bronze', 'iron', 'steel', 'crystal', 'frozen', 'fiery',
        'windy', 'watery', 'earthy', 'magical', 'mythical', 'legendary', 'epic', 'rare'
    ],
    'noun': [
        'dog', 'idea', 'mountain', 'river', 'book', 'computer', 'star', 'ocean',
        'dragon', 'phoenix', 'wizard', 'warrior', 'knight', 'mage', 'rogue', 'archer',
        'planet', 'galaxy', 'comet', 'nebula', 'code', 'algorithm', 'data', 'network',
        'forest', 'desert', 'island', 'volcano', 'castle', 'temple', 'crystal', 'orb'
    ],
    'adverb': [
        'quickly', 'silently', 'happily', 'bravely', 'cleverly', 'brightly',
        'swiftly', 'slowly', 'loudly', 'quietly', 'boldly', 'wisely', 'madly',
        'gladly', 'sadly', 'proudly', 'simply', 'truly', 'deeply', 'highly'
    ],
    'cliche': [
        'piece of cake', 'break a leg', 'hit the road', 'once in a blue moon',
        'bite the bullet', 'cost an arm and a leg', 'cry over spilled milk',
        'devil in disguise', 'elephant in the room', 'fit as a fiddle',
        'go down in flames', 'heart of gold', 'needle in a haystack'
    ],
    'animal': [
        'lion', 'eagle', 'dolphin', 'wolf', 'fox', 'bear', 'tiger', 'panther',
        'falcon', 'hawk', 'raven', 'owl', 'shark', 'orca', 'whale', 'octopus',
        'dragon', 'griffin', 'unicorn', 'phoenix', 'basilisk', 'hippogriff'
    ],
    'verb': [
        'run', 'jump', 'think', 'create', 'explore', 'discover', 'build', 'design',
        'code', 'hack', 'learn', 'teach', 'write', 'read', 'sing', 'dance',
        'fight', 'defend', 'attack', 'protect', 'save', 'rescue', 'find'
    ],
    'concreteNoun': [
        'rock', 'table', 'phone', 'car', 'house', 'tree', 'sword', 'shield',
        'book', 'crystal', 'gem', 'coin', 'key', 'lock', 'door', 'gate',
        'mirror', 'lantern', 'torch', 'scroll', 'potion', 'amulet', 'ring'
    ],
    'containerType': [
        'jar', 'box', 'bottle', 'can', 'case', 'bag', 'chest', 'vault',
        'capsule', 'pod', 'tube', 'flask', 'vial', 'urn', 'crate', 'barrel'
    ]
}

import random
import re

def title_case(text):
    """Convert text to title case (first letter capitalized)"""
    return text[0].upper() + text[1:] if text else text

def upper_case(text):
    """Convert text to uppercase"""
    return text.upper()

def plural_form(text):
    """Simple pluralization (you might want a more sophisticated approach)"""
    if text.endswith(('s', 'x', 'z', 'ch', 'sh')):
        return text + 'es'
    elif text.endswith('y') and len(text) > 1 and text[-2] not in 'aeiou':
        return text[:-1] + 'ies'
    else:
        return text + 's'

def select_many(min_digits, max_digits):
    """Generate random number string with specified digit count"""
    num_digits = random.randint(min_digits, max_digits)
    return ''.join(str(random.randint(0, 9)) for _ in range(num_digits))

def replace_text(text, pattern, replacement):
    """Replace text using regex pattern"""
    return re.sub(pattern, replacement, text)

def generate_username():
    """Generate a random username following the Perchance patterns"""
    
    # Get random words from each category
    adjective = random.choice(word_lists['adjective'])
    noun = random.choice(word_lists['noun'])
    adverb = random.choice(word_lists['adverb'])
    cliche = random.choice(word_lists['cliche'])
    animal = random.choice(word_lists['animal'])
    concrete_noun = random.choice(word_lists['concreteNoun'])
    container_type = random.choice(word_lists['containerType'])
    
    # Define patterns with their probabilities
    patterns = [
        (0.5, lambda: f"{'The' if random.random() < 0.5 else ''}{title_case(adjective)}{title_case(noun)}"),
        (0.5, lambda: f"{'the' if random.random() < 0.5 else ''}{adjective}_{noun}"),
        (1.0, lambda: f"{adjective}_{noun}"),
        (1.0, lambda: f"{title_case(adjective)}{title_case(noun)}"),
        (0.4, lambda: f"{title_case(adverb)}{title_case(adjective)}"),
        (1.0, lambda: f"{adjective}{noun}{'_' if random.random() < 0.2 else ''}{select_many(1, 4)}"),
        (0.25, lambda: f"{adverb}_{adjective}_{noun}"),
        (0.25, lambda: f"{adverb}{adjective}{noun}"),
        (0.1, lambda: f"PM_ME_YOUR_{plural_form(noun).upper()}"),
        (0.1, lambda: f"PM_ME_YOUR_{adjective.upper()}_{plural_form(noun).upper()}"),
        (0.025, lambda: f"throwaway{'_' if random.random() < 0.2 else ''}{select_many(7, 12)}"),
        (0.1, lambda: replace_text(replace_text(cliche, r'[^a-z ]', ''), ' ', '_')),
        (0.005, lambda: f"2{adjective}4u"),
        (0.05, lambda: f"{container_type}_of_{plural_form(concrete_noun)}"),
        (0.1, lambda: f"{title_case(adjective)}{title_case(replace_text(animal, r'[^a-z]', ''))}")
    ]
    
    # Calculate total weight for probability distribution
    total_weight = sum(weight for weight, _ in patterns)
    
    # Select pattern based on weights
    rand_val = random.uniform(0, total_weight)
    current = 0
    
    for weight, pattern_func in patterns:
        current += weight
        if rand_val <= current:
            return pattern_func()
    
    # Fallback
    return f"{adjective}_{noun}"

