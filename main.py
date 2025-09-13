import tkinter as tk
from tkinter import messagebox, filedialog
from PIL import Image, ImageTk
from pathlib import Path
from collections import Counter
import hashlib


class ImageLabeler:
    def __init__(self, root):
        self.root = root
        self.root.title("Программа для разметки изображений")
        self.root.geometry("1400x700")  # Увеличил ширину окна для статистики

        # Выбор папки с задачей
        selected_path = filedialog.askdirectory(title="Выберите папку задачи", initialdir="Tasks")
        self.task_path = Path(selected_path) if selected_path else Path("Tasks/job_1")
        self.image_path = self.task_path / "images"
        self.classes_file = self.task_path / "classes.txt"

        # Загрузка классов
        self.classes = self.load_classes()
        self.current_class = tk.StringVar(value=self.classes[0] if self.classes else "")
        self.class_colors = {cls: self.generate_color(cls) for cls in self.classes}

        # Загрузка списка изображений
        self.image_files = [f for f in self.image_path.glob("*.jpg") if f.is_file()]
        self.current_image_index = 0
        self.current_image = None
        self.image_tk = None
        self.image_width = 0
        self.image_height = 0
        self.scale = 1
        self.offset_x = 0
        self.offset_y = 0

        # Переменные для разметки
        self.start_x = None
        self.start_y = None
        self.current_rect = None
        self.annotations = []
        self.selected_rect = None
        self.resize_handle = None
        self.resize_corner = None

        # Создание интерфейса
        self.create_widgets()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        # Глобальные горячие клавиши для переключения изображений
        self.root.bind_all("<Left>", lambda e: self.prev_image())
        self.root.bind_all("<Right>", lambda e: self.next_image())

        # Загрузка первого изображения
        if self.image_files:
            self.load_image(self.image_files[self.current_image_index])

    def load_classes(self):
        """Загружает классы из файла classes.txt"""
        if self.classes_file.exists():
            with open(self.classes_file, 'r') as f:
                return [line.strip() for line in f if line.strip()]
        return []

    def generate_color(self, name):
        """Генерирует детерминированный цвет для класса"""
        h = hashlib.md5(name.encode()).hexdigest()
        r = int(h[0:2], 16)
        g = int(h[2:4], 16)
        b = int(h[4:6], 16)
        return f"#{r:02x}{g:02x}{b:02x}"

    def create_widgets(self):
        """Создает элементы интерфейса"""
        # Левый фрейм для классов и подсказок
        self.left_frame = tk.Frame(self.root, width=200)
        self.left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

        # Список классов
        tk.Label(self.left_frame, text="Классы:").pack(anchor=tk.W)
        self.classes_var = tk.StringVar(value=self.classes)
        self.class_listbox = tk.Listbox(self.left_frame, listvariable=self.classes_var, height=10)
        self.class_listbox.pack(fill=tk.X, pady=5)
        self.class_listbox.bind('<<ListboxSelect>>', self.on_class_select)
        for idx, cls in enumerate(self.classes):
            color = self.class_colors.get(cls, "black")
            self.class_listbox.itemconfig(idx, fg=color)

        # Подсказка по использованию программы
        tk.Label(
            self.left_frame,
            text=(
                "ЛКМ - рисовать/перемещать\n"
                "ПКМ - удалить рамку\n"
                "Колесо - след. изображение\n"
                "Аннотации сохраняются\n"
                "автоматически"
            ),
            justify=tk.LEFT,
            wraplength=180,
        ).pack(pady=10)

        # Центральный фрейм для изображения
        self.center_frame = tk.Frame(self.root)
        self.center_frame.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)

        # Холст для изображения
        self.canvas = tk.Canvas(self.center_frame, bg="gray")
        self.canvas.pack(expand=True, fill=tk.BOTH)
        self.canvas.bind("<Configure>", self.on_canvas_resize)

        # Привязка событий мыши
        self.canvas.bind("<Button-1>", self.start_action)
        self.canvas.bind("<B1-Motion>", self.draw_or_resize_or_drag)
        self.canvas.bind("<ButtonRelease-1>", self.end_action)
        self.canvas.bind("<MouseWheel>", self.scroll_image)  # Прокрутка колесиком мыши
        self.canvas.bind("<Button-3>", self.delete_box)
        self.canvas.bind("<Motion>", self.draw_crosshair)
        self.canvas.bind("<Leave>", lambda e: self.canvas.delete("crosshair"))

        # Правый фрейм для статистики
        self.right_frame = tk.Frame(self.root, width=200)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=5, pady=5)
        tk.Label(self.right_frame, text="Статистика:").pack(anchor=tk.W)
        self.stats_text = tk.Text(self.right_frame, width=30, height=15, state=tk.DISABLED)
        self.stats_text.pack(anchor=tk.W, pady=5)

        # Обновление статистики
        self.update_stats()

    def load_image(self, image_path):
        """Загружает изображение на холст"""
        self.current_image = Image.open(image_path)
        self.image_width, self.image_height = self.current_image.size
        self.display_image()

        # Загрузка аннотаций, если они есть
        annotation_file = self.image_path / f"{image_path.stem}.txt"
        self.annotations = []
        if annotation_file.exists():
            with open(annotation_file, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) == 5:
                        class_id = int(parts[0])
                        x_center, y_center, width, height = map(float, parts[1:])
                        x1 = (x_center - width / 2) * self.image_width
                        y1 = (y_center - height / 2) * self.image_height
                        x2 = (x_center + width / 2) * self.image_width
                        y2 = (y_center + height / 2) * self.image_height
                        self.annotations.append({
                            'class': self.classes[class_id] if class_id < len(self.classes) else "unknown",
                            'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2
                        })
        self.redraw_annotations()
        self.update_stats()

    def display_image(self):
        """Отображает текущее изображение с учетом размеров холста"""
        self.canvas.delete("all")
        self.root.update_idletasks()
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        if canvas_w <= 1 or canvas_h <= 1:
            return
        scale = min(canvas_w / self.image_width, canvas_h / self.image_height)
        self.scale = scale
        new_w = int(self.image_width * scale)
        new_h = int(self.image_height * scale)
        self.offset_x = (canvas_w - new_w) / 2
        self.offset_y = (canvas_h - new_h) / 2
        display_image = self.current_image.resize((new_w, new_h), Image.Resampling.LANCZOS)
        self.image_tk = ImageTk.PhotoImage(display_image)
        self.canvas.create_image(self.offset_x, self.offset_y, image=self.image_tk, anchor=tk.NW, tags="image")

    def image_to_canvas(self, x, y):
        return x * self.scale + self.offset_x, y * self.scale + self.offset_y

    def canvas_to_image(self, x, y):
        return (x - self.offset_x) / self.scale, (y - self.offset_y) / self.scale

    def on_canvas_resize(self, event):
        if self.current_image:
            self.display_image()
            self.redraw_annotations()

    def redraw_annotations(self):
        """Перерисовывает все аннотации на холсте"""
        self.canvas.delete("rectangle", "handle", "text")
        for i, ann in enumerate(self.annotations):
            x1, y1 = self.image_to_canvas(ann['x1'], ann['y1'])
            x2, y2 = self.image_to_canvas(ann['x2'], ann['y2'])
            color = self.class_colors.get(ann['class'], "red")
            self.canvas.create_rectangle(
                x1, y1, x2, y2,
                outline=color, width=2, tags=("rectangle", f"rect_{i}")
            )
            self.canvas.create_rectangle(
                x2 - 5, y2 - 5, x2 + 5, y2 + 5,
                fill="blue", tags=("handle", f"handle_{i}_br")
            )
            self.canvas.create_text(
                x1,
                y1 - 10,
                text=ann['class'],
                fill=color,
                anchor=tk.SW,
                tags="text",
                font=("TkDefaultFont", 10, "bold"),
            )

    def start_action(self, event):
        """Начало действия: рисование, выбор или перетаскивание"""
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)

        # Проверяем маркеры изменения размера
        items = self.canvas.find_overlapping(x, y, x, y)
        for item in items:
            tags = self.canvas.gettags(item)
            if "handle" in tags:
                self.selected_rect = int(tags[1].split("_")[1])
                self.resize_corner = tags[1].split("_")[2]
                self.start_x, self.start_y = x, y
                return

        # Проверяем попадание в существующий прямоугольник
        ix, iy = self.canvas_to_image(x, y)
        for i, ann in enumerate(self.annotations):
            if ann['x1'] <= ix <= ann['x2'] and ann['y1'] <= iy <= ann['y2']:
                self.selected_rect = i
                rect_x1, rect_y1 = self.image_to_canvas(ann['x1'], ann['y1'])
                self.start_x = x - rect_x1
                self.start_y = y - rect_y1
                self.resize_corner = None
                return

        # Клик вне изображения — игнорируем
        if not (self.offset_x <= x <= self.offset_x + self.image_width * self.scale and
                self.offset_y <= y <= self.offset_y + self.image_height * self.scale):
            return

        # Начало рисования нового прямоугольника
        self.selected_rect = None
        self.start_x, self.start_y = x, y
        color = self.class_colors.get(self.current_class.get(), "red")
        self.current_rect = self.canvas.create_rectangle(
            x, y, x, y, outline=color, width=2, tags="rectangle"
        )

    def draw_or_resize_or_drag(self, event):
        """Рисование, изменение размера или перетаскивание"""
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)

        if self.current_rect:  # Рисование нового прямоугольника
            self.canvas.coords(self.current_rect, self.start_x, self.start_y, x, y)
        elif self.selected_rect is not None:
            ann = self.annotations[self.selected_rect]
            if self.resize_corner:  # Изменение размера
                if self.resize_corner == "br":
                    ix, iy = self.canvas_to_image(x, y)
                    ann['x2'], ann['y2'] = ix, iy
                self.redraw_annotations()
            else:  # Перетаскивание
                new_x1 = x - self.start_x
                new_y1 = y - self.start_y
                ix1, iy1 = self.canvas_to_image(new_x1, new_y1)
                width = ann['x2'] - ann['x1']
                height = ann['y2'] - ann['y1']
                ann['x1'], ann['y1'] = ix1, iy1
                ann['x2'] = ix1 + width
                ann['y2'] = iy1 + height
                self.redraw_annotations()

    def end_action(self, event):
        """Завершение действия"""
        if self.current_rect:
            x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
            if abs(x - self.start_x) > 5 and abs(y - self.start_y) > 5:
                x1, y1 = self.canvas_to_image(self.start_x, self.start_y)
                x2, y2 = self.canvas_to_image(x, y)
                self.annotations.append({
                    'class': self.current_class.get(),
                    'x1': min(x1, x2),
                    'y1': min(y1, y2),
                    'x2': max(x1, x2),
                    'y2': max(y1, y2)
                })
                self.redraw_annotations()
                self.update_stats()
            self.canvas.delete(self.current_rect)
            self.current_rect = None
        self.selected_rect = None
        self.resize_corner = None

    def delete_box(self, event):
        """Удаление прямоугольника правой кнопкой мыши"""
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        # Конвертируем координаты в систему изображения,
        # чтобы не зависеть от масштабирования и смещения
        ix, iy = self.canvas_to_image(x, y)
        # Ищем аннотацию, содержащую точку
        for idx in range(len(self.annotations) - 1, -1, -1):
            ann = self.annotations[idx]
            if ann['x1'] <= ix <= ann['x2'] and ann['y1'] <= iy <= ann['y2']:
                del self.annotations[idx]
                self.redraw_annotations()
                self.update_stats()
                return

    def draw_crosshair(self, event):
        """Отрисовка вспомогательных линий под курсором"""
        self.canvas.delete("crosshair")
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        self.canvas.create_line(0, y, w, y, fill="blue", dash=(2, 2), tags="crosshair")
        self.canvas.create_line(x, 0, x, h, fill="blue", dash=(2, 2), tags="crosshair")

    def on_class_select(self, event):
        """Обработка выбора класса из списка"""
        selection = self.class_listbox.curselection()
        if selection:
            self.current_class.set(self.class_listbox.get(selection[0]))

    def scroll_image(self, event):
        """Прокрутка изображений колесиком мыши"""
        if not self.image_files:
            return
        self.save_annotations()
        if event.delta > 0:
            self.current_image_index = (self.current_image_index - 1) % len(self.image_files)
        else:
            self.current_image_index = (self.current_image_index + 1) % len(self.image_files)
        self.load_image(self.image_files[self.current_image_index])

    def prev_image(self):
        """Переключение на предыдущее изображение"""
        if self.image_files:
            self.save_annotations()
            self.current_image_index = (self.current_image_index - 1) % len(self.image_files)
            self.load_image(self.image_files[self.current_image_index])

    def next_image(self):
        """Переключение на следующее изображение"""
        if self.image_files:
            self.save_annotations()
            self.current_image_index = (self.current_image_index + 1) % len(self.image_files)
            self.load_image(self.image_files[self.current_image_index])

    def save_annotations(self, show_message=False):
        """Сохранение аннотаций в файл .txt в формате YOLO"""
        if self.image_files:
            annotation_file = self.image_path / f"{self.image_files[self.current_image_index].stem}.txt"
            with open(annotation_file, 'w') as f:
                for ann in self.annotations:
                    class_id = self.classes.index(ann['class']) if ann['class'] in self.classes else 0
                    x_center = (ann['x1'] + ann['x2']) / 2 / self.image_width
                    y_center = (ann['y1'] + ann['y2']) / 2 / self.image_height
                    width = (ann['x2'] - ann['x1']) / self.image_width
                    height = (ann['y2'] - ann['y1']) / self.image_height
                    f.write(f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n")
            if show_message:
                messagebox.showinfo("Успех", "Аннотации сохранены")
            self.update_stats()

    def update_stats(self):
        """Обновляет статистику"""
        # Подсчет размеченных изображений
        labeled_images = sum(1 for img in self.image_files if (self.image_path / f"{img.stem}.txt").exists())

        # Подсчет классов в текущем изображении
        class_counts = Counter(ann['class'] for ann in self.annotations)

        # Подсчет классов во всех аннотациях
        all_class_counts = Counter()
        for img in self.image_files:
            ann_file = self.image_path / f"{img.stem}.txt"
            if ann_file.exists():
                with open(ann_file, 'r') as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) == 5:
                            class_id = int(parts[0])
                            if class_id < len(self.classes):
                                all_class_counts[self.classes[class_id]] += 1

        # Формирование текста статистики с подсветкой классов
        self.stats_text.config(state=tk.NORMAL)
        self.stats_text.delete("1.0", tk.END)
        self.stats_text.insert(
            tk.END,
            f"Текущее изображение: {self.current_image_index + 1}/{len(self.image_files)}\n",
        )
        self.stats_text.insert(
            tk.END,
            f"Размеченных изображений: {labeled_images}/{len(self.image_files)}\n\n",
        )
        self.stats_text.insert(tk.END, "Классы в текущем изображении:\n")
        for cls, count in class_counts.items():
            color = self.class_colors.get(cls, "black")
            self.stats_text.tag_config(cls, foreground=color)
            self.stats_text.insert(tk.END, "  ")
            self.stats_text.insert(tk.END, cls, cls)
            self.stats_text.insert(tk.END, f": {count}\n")
        self.stats_text.insert(tk.END, "\nКлассы во всех аннотациях:\n")
        for cls, count in all_class_counts.items():
            color = self.class_colors.get(cls, "black")
            self.stats_text.tag_config(cls, foreground=color)
            self.stats_text.insert(tk.END, "  ")
            self.stats_text.insert(tk.END, cls, cls)
            self.stats_text.insert(tk.END, f": {count}\n")
        self.stats_text.config(state=tk.DISABLED)

    def on_close(self):
        """Сохранение данных при закрытии окна"""
        self.save_annotations()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = ImageLabeler(root)
    root.mainloop()
