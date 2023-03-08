import unittest

class TestScrapingFunctions(unittest.TestCase):
    
    # Test the gen_url function
    def test_gen_url(self):
        format_keys = ['Modern', 'Legacy', 'Standard']
        urls = gen_url(format_keys)
        self.assertIsInstance(urls, list)
        self.assertTrue(all([isinstance(url, str) for url in urls]))
        self.assertTrue(all([url.startswith('https://www.mtggoldfish.com/metagame/') for url in urls]))
    
    # Test the get_archetypes function
    def test_get_archetypes(self):
        url = 'https://www.mtggoldfish.com/metagame/standard#paper'
        archetypes = get_archetypes(url)
        self.assertIsInstance(archetypes, list)
        self.assertTrue(all([isinstance(archetype, str) for archetype in archetypes]))
        self.assertTrue(all(['archetype?' in archetype for archetype in archetypes]))
    
    # Test the get_decks function
    def test_get_decks(self):
        archetypes = ['https://www.mtggoldfish.com/archetype/standard-izzet-dragonsgMP-#paper']
        decks = get_decks(archetypes)
        self.assertIsInstance(decks, list)
        self.assertTrue(all([isinstance(deck, str) for deck in decks]))
        self.assertTrue(all(['d=' in deck for deck in decks]))
    
    # Test the get_mtgo_deck_from_webpage function
    def test_get_mtgo_deck_from_webpage(self):
        url = 'https://www.mtggoldfish.com/deck/download/1691732'
        driver = webdriver.Chrome()
        deck = get_mtgo_deck_from_webpage(url, driver)
        self.assertIsInstance(deck, str)
        driver.quit()
    
    # Test the get_decklists function
    def test_get_decklists(self):
        decks = ['https://www.mtggoldfish.com/deck/download/1691732']
        decklists = get_decklists(decks)
        self.assertIsInstance(decklists, list)
        self.assertTrue(all([isinstance(decklist, str) for decklist in decklists]))
    
if __name__ == '__main__':
    unittest.main()
