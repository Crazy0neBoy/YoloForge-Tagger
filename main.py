import tkinter as tk
from tkinter import messagebox, filedialog
from PIL import Image, ImageTk
from pathlib import Path
from collections import Counter


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

        # Загрузка списка изображений
        self.image_files = [f for f in self.image_path.glob("*.jpg") if f.is_file()]
        self.current_image_index = 0
        self.current_image = None
        self.image_tk = None
        self.image_width = 0
        self.image_height = 0
        self.scale_x = 1
        self.scale_y = 1

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

        # Загрузка первого изображения
        if self.image_files:
            self.load_image(self.image_files[self.current_image_index])

    def load_classes(self):
        """Загружает классы из файла classes.txt"""
        if self.classes_file.exists():
            with open(self.classes_file, 'r') as f:
                return [line.strip() for line in f if line.strip()]
        return []

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
        self.stats_label = tk.Label(self.right_frame, text="", justify=tk.LEFT)
        self.stats_label.pack(anchor=tk.W, pady=5)

        # Кнопки навигации и счетчик изображений
        self.nav_frame = tk.Frame(self.root)
        self.nav_frame.pack(side=tk.BOTTOM, fill=tk.X)
        tk.Button(self.nav_frame, text="Предыдущее", command=self.prev_image).pack(side=tk.LEFT, padx=5)
        self.image_counter = tk.Label(self.nav_frame, text="")
        self.image_counter.pack(side=tk.LEFT, padx=5)
        tk.Button(self.nav_frame, text="Следующее", command=self.next_image).pack(side=tk.LEFT, padx=5)

        # Обновление статистики и счетчика
        self.update_stats()
        self.update_image_counter()

    def load_image(self, image_path):
        """Загружает изображение на холст"""
        self.canvas.delete("all")
        self.current_image = Image.open(image_path)
        self.image_width, self.image_height = self.current_image.size
        self.scale_x = 800 / self.image_width
        self.scale_y = 600 / self.image_height
        display_image = self.current_image.resize((int(self.image_width * self.scale_x), int(self.image_height * self.scale_y)), Image.Resampling.LANCZOS)
        self.image_tk = ImageTk.PhotoImage(display_image)
        self.canvas.create_image(0, 0, image=self.image_tk, anchor=tk.NW, tags="image")

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
                        # Конвертация из нормализованных координат YOLO в пиксельные
                        x1 = (x_center - width / 2) * self.image_width * self.scale_x
                        y1 = (y_center - height / 2) * self.image_height * self.scale_y
                        x2 = (x_center + width / 2) * self.image_width * self.scale_x
                        y2 = (y_center + height / 2) * self.image_height * self.scale_y
                        self.annotations.append({
                            'class': self.classes[class_id] if class_id < len(self.classes) else "unknown",
                            'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2
                        })
        self.redraw_annotations()
        self.update_image_counter()
        self.update_stats()

    def redraw_annotations(self):
        """Перерисовывает все аннотации на холсте"""
        self.canvas.delete("rectangle", "handle", "text")
        for i, ann in enumerate(self.annotations):
            rect_id = self.canvas.create_rectangle(
                ann['x1'], ann['y1'], ann['x2'], ann['y2'],
                outline="red", width=2, tags=("rectangle", f"rect_{i}")
            )
            # Добавление маркеров для изменения размера
            self.canvas.create_rectangle(
                ann['x2'] - 5, ann['y2'] - 5, ann['x2'] + 5, ann['y2'] + 5,
                fill="blue", tags=("handle", f"handle_{i}_br")
            )
            self.canvas.create_text(
                ann['x1'], ann['y1'] - 10,
                text=ann['class'], fill="red", anchor=tk.SW, tags="text"
            )

    def start_action(self, event):
        """Начало действия: рисование, выбор или перетаскивание"""
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)

        # Проверка, попал ли клик на маркер изменения размера
        items = self.canvas.find_overlapping(x - 5, y - 5, x + 5, y + 5)
        for item in items:
            tags = self.canvas.gettags(item)
            if "handle" in tags:
                self.selected_rect = int(tags[1].split("_")[1])
                self.resize_corner = tags[1].split("_")[2]
                self.start_x, self.start_y = x, y
                return

        # Проверка, попал ли клик на прямоугольник для перетаскивания
        for i, ann in enumerate(self.annotations):
            if (ann['x1'] <= x <= ann['x2'] and ann['y1'] <= y <= ann['y2']):
                self.selected_rect = i
                self.start_x, self.start_y = x - ann['x1'], y - ann['y1']
                self.resize_corner = None
                return

        # Начало рисования нового прямоугольника
        self.selected_rect = None
        self.start_x, self.start_y = x, y
        self.current_rect = self.canvas.create_rectangle(
            x, y, x, y, outline="red", width=2, tags="rectangle"
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
                    ann['x2'], ann['y2'] = x, y
                self.redraw_annotations()
            else:  # Перетаскивание
                dx, dy = x - self.start_x, y - self.start_y
                width = ann['x2'] - ann['x1']
                height = ann['y2'] - ann['y1']
                ann['x1'], ann['y1'] = dx, dy
                ann['x2'] = ann['x1'] + width
                ann['y2'] = ann['y1'] + height
                self.redraw_annotations()

    def end_action(self, event):
        """Завершение действия"""
        if self.current_rect:
            x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
            if abs(x - self.start_x) > 5 and abs(y - self.start_y) > 5:  # Минимальный размер прямоугольника
                self.annotations.append({
                    'class': self.current_class.get(),
                    'x1': min(self.start_x, x),
                    'y1': min(self.start_y, y),
                    'x2': max(self.start_x, x),
                    'y2': max(self.start_y, y)
                })
                self.canvas.create_text(
                    min(self.start_x, x), min(self.start_y, y) - 10,
                    text=self.current_class.get(), fill="red", anchor=tk.SW, tags="text"
                )
                self.redraw_annotations()
                self.update_stats()
            self.canvas.delete(self.current_rect)
            self.current_rect = None
        self.selected_rect = None
        self.resize_corner = None

    def delete_box(self, event):
        """Удаление прямоугольника правой кнопкой мыши"""
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        for i, ann in enumerate(self.annotations):
            if ann['x1'] <= x <= ann['x2'] and ann['y1'] <= y <= ann['y2']:
                del self.annotations[i]
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
        if event.delta > 0 and self.current_image_index > 0:
            self.save_annotations()
            self.current_image_index -= 1
            self.load_image(self.image_files[self.current_image_index])
        elif event.delta < 0 and self.current_image_index < len(self.image_files) - 1:
            self.save_annotations()
            self.current_image_index += 1
            self.load_image(self.image_files[self.current_image_index])

    def prev_image(self):
        """Переключение на предыдущее изображение"""
        if self.current_image_index > 0:
            self.save_annotations()
            self.current_image_index -= 1
            self.load_image(self.image_files[self.current_image_index])

    def next_image(self):
        """Переключение на следующее изображение"""
        if self.current_image_index < len(self.image_files) - 1:
            self.save_annotations()
            self.current_image_index += 1
            self.load_image(self.image_files[self.current_image_index])

    def save_annotations(self, show_message=False):
        """Сохранение аннотаций в файл .txt в формате YOLO"""
        if self.image_files:
            annotation_file = self.image_path / f"{self.image_files[self.current_image_index].stem}.txt"
            with open(annotation_file, 'w') as f:
                for ann in self.annotations:
                    class_id = self.classes.index(ann['class']) if ann['class'] in self.classes else 0
                    # Конвертация в нормализованные координаты YOLO
                    x1 = ann['x1'] / self.scale_x
                    y1 = ann['y1'] / self.scale_y
                    x2 = ann['x2'] / self.scale_x
                    y2 = ann['y2'] / self.scale_y
                    x_center = (x1 + x2) / 2 / self.image_width
                    y_center = (y1 + y2) / 2 / self.image_height
                    width = (x2 - x1) / self.image_width
                    height = (y2 - y1) / self.image_height
                    f.write(f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n")
            if show_message:
                messagebox.showinfo("Успех", "Аннотации сохранены")
            self.update_stats()

    def update_image_counter(self):
        """Обновляет счетчик изображений"""
        self.image_counter.config(text=f"{self.current_image_index + 1}/{len(self.image_files)}")

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

        # Формирование текста статистики
        stats_text = (
            f"Размеченных изображений: {labeled_images}/{len(self.image_files)}\n\n"
            f"Классы в текущем изображении:\n"
        )
        for cls, count in class_counts.items():
            stats_text += f"  {cls}: {count}\n"
        stats_text += "\nКлассы во всех аннотациях:\n"
        for cls, count in all_class_counts.items():
            stats_text += f"  {cls}: {count}\n"

        self.stats_label.config(text=stats_text)

    def on_close(self):
        """Сохранение данных при закрытии окна"""
        self.save_annotations()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = ImageLabeler(root)
    root.mainloop()
