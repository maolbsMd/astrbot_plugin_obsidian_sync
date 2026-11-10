from reportlab.graphics.shapes import Drawing, Line, Circle, String, Rect
from reportlab.graphics import renderPM
import sys

def draw_simple_circuit(filename):
    d = Drawing(400, 200)
    # 画一个简单的回路
    d.add(Line(50, 150, 350, 150))
    d.add(Line(50, 50, 350, 50))
    d.add(Line(50, 50, 50, 150))
    d.add(Line(350, 50, 350, 150))
    d.add(String(150, 160, "R = 1 Ω", fontSize=12))
    renderPM.saveToFile(d, filename, 'PNG')

if __name__ == "__main__":
    draw_simple_circuit(sys.argv[1])
