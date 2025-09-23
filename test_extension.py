import inkex

class TestExtension(inkex.EffectExtension):
    def effect(self):
        self.msg("Расширение запущено")
        root = self.svg.getroot()
        self.msg(f"Корневой элемент: {root.tag}")
        for el in root.iter():
            self.msg(f"Нашли элемент: <{el.tag}> id={el.attrib.get('id','(без id)')}")

if __name__ == '__main__':
    TestExtension().run()
