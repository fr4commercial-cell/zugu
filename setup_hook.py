class MyBot:
    async def setup_hook(self):
        try:
            synced = await self.tree.sync()  # GLOBAL SYNC
            print(f"🌍 Comandi globali sincronizzati: {len(synced)}")
        except Exception as e:
            print(f"❌ Errore nella sincronizzazione globale: {e}")
