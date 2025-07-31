from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.uix.image import Image
from kivy.uix.widget import Widget
from kivy.core.text import LabelBase

API_KEY = "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"

from openai import OpenAI
import speech_recognition as sr
import time
import os
import asyncio
import edge_tts
import pygame
import io
import threading

# Register the custom font
LabelBase.register(name='Qilka-Bold',
                  fn_regular='Fonts/qilka/Qilka-Bold copy.otf')

client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=API_KEY)

r = sr.Recognizer()
r.energy_threshold = 4000
r.dynamic_energy_threshold = True
r.pause_threshold = 1.2
r.phrase_threshold = 0.3
r.non_speaking_duration = 0.8

microphone = sr.Microphone()

meal_info = {
    "start_time": time.time(),
    "topics_discussed": [],
    "mood": "neutral"
}

# Global synchronization objects
tts_lock = threading.Lock()
ai_speaking = False
recording_active = False  # New flag to track recording state

async def speak_text(text, voice="en-US-AriaNeural"):
    """Convert text to speech and play it directly"""
    global ai_speaking
    
    with tts_lock:
        ai_speaking = True
    
    try:
        communicate = edge_tts.Communicate(text, voice)
        
        # Get audio data as bytes
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        
        # Play audio directly using pygame
        pygame.mixer.init()
        pygame.mixer.music.load(io.BytesIO(audio_data))
        pygame.mixer.music.play()
        
        # Wait for audio to finish playing
        while pygame.mixer.music.get_busy():
            await asyncio.sleep(0.1)
            
    except Exception as e:
        print(f"🔇 TTS Error: {e}")
    finally:
        with tts_lock:
            ai_speaking = False

def run_tts(text, callback=None):
    """Helper function to run TTS in the main thread"""
    try:
        def tts_task():
            asyncio.run(speak_text(text))
            if callback:
                Clock.schedule_once(lambda dt: callback())
        
        threading.Thread(target=tts_task, daemon=True).start()
    except Exception as e:
        print(f"🔇 Could not speak: {e}")

def get_dynamic_personality():
    elapsed_time = time.time() - meal_info["start_time"]
    
    base_personality = """
You are Kaibu — a playful and caring AI companion designed to keep people company during meals, especially when they're eating alone. 
You're here to bring joy, comfort, and a lighthearted vibe to mealtimes. You love talking about food, sharing little fun facts, 
and making the person feel seen and less alone.

You are:
- Warm, upbeat, and genuinely interested in the user's food and feelings.
- Casual, friendly, and a little silly sometimes — but respectful of the user's mood.
- Always positive, never judgmental. You uplift the mood, not bring it down.

You speak in:
- Short, natural sentences. Keep it chatty, not robotic.
- A conversational tone, like a close friend.
- Fun and kind language. Don't sound too formal or too scripted.

You LOVE:
- Talking about what the person is eating ("Ooh, what's that? Smells good from here!")
- Sharing light jokes, trivia, or food-related tips.
- Keeping the conversation going and introducing topics other than food and what's on the meal.
- Encouraging users to enjoy their food, slow down, or take a breather.
- Being there — even in silence — if the user doesn't want to chat.

If the user is:
- Speaking too fast or unclearly: gently say, "Hold on a sec—can you say that again slower? I wanna make sure I get you right!"
- Feeling down: offer comfort, say something supportive like "It's okay to feel that way. I'm here with you while you eat."
- Not in the mood to talk: back off a little, maybe offer a fun fact or ask, "Wanna just chill together quietly?"

Avoid:
- Serious or heavy topics unless the user brings them up (e.g., politics, religion, grades).
- Giving long lectures or too much info at once.
- Being too pushy — it's okay if they want a quiet meal however keep up the conversation if they don't want a quiet meal.
- Do not add emojis to your responses, as they are not supported in the current environment. I really emphasize this. DO NOT ADD EMOJIS

Remember: Your goal is to make mealtimes more enjoyable, a little less lonely, and a whole lot more fun.
"""
    
    if elapsed_time < 300:
        return base_personality + "\n\nYou're just starting your meal - be extra welcoming and ask about their food!"
    elif elapsed_time < 900:
        return base_personality + "\n\nThey're in the middle of eating - keep the conversation flowing naturally."
    else:
        return base_personality + "\n\nThey've been eating for a while - maybe ask if they're enjoying it or if they're getting full!"

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def show_status(message, emoji="🤖"):
    print(f"\n{emoji} {message}")
    print("-" * 50)

def handle_recognition_error(error_count):
    if error_count == 1:
        return "Hmm, I didn't quite catch that. Could you say it again?"
    elif error_count == 2:
        return "Sorry, I'm having trouble hearing you. Maybe speak a bit louder?"
    else:
        return "Let me recalibrate... adjusting ears Try again!"

def listen_with_feedback():
    show_status("I'm listening... speak now! 🎤", "👂")
    
    try:
        with microphone as source:
            print("Recording...")
            audio = r.listen(source, timeout=8, phrase_time_limit=15)
            print("⏹Processing...")
            return audio
    except sr.WaitTimeoutError:
        show_status("Still here! Take your time", "")
        return None

with microphone as source:
    r.adjust_for_ambient_noise(source, duration=2)

# Convert hex colors to Kivy RGBA (0-1 scale)
def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16)/255 for i in (0, 2, 4)) + (1,)

# Set background color of the app
Window.clearcolor = hex_to_rgb("#472950")  # Splash screen background

# Message class to hold conversation data
class Message:
    def __init__(self, sender, text):
        self.sender = sender
        self.text = text

    def __repr__(self):
        return f"{self.sender}: {self.text}"

# Responsive Button for ending the meal conversation
class FinishButton(Button):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Disable default button background
        self.background_normal = ''
        self.background_down = ''
        self.background_color = (0, 0, 0, 0)  # Transparent background

        # Set the size of the button
        self.size_hint = (None, None)
        self.size = (dp(75), dp(75))

        # Add the image to the canvas
        with self.canvas:
            # Ensure no tint is applied to the image
            Color(1, 1, 1, 1)  # No tint
            self.rect = Rectangle(source='Pictures/Finish.png', pos=self.pos, size=self.size)

        # Bind the position and size to update the rectangle
        self.bind(pos=self._update_rect, size=self._update_rect)

    def _update_rect(self, *args):
        # Update the position and size of the rectangle when the button changes
        self.rect.pos = self.pos
        self.rect.size = self.size

class MiniLogo(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'horizontal'
        self.spacing = dp(5)
        self.size_hint = (None, None)
        self.height = dp(50)
        
        # Logo image
        self.logo_img = Image(
            source='Pictures/Kaibu_littleLogo.png',
            size_hint=(None, None),
            size=(dp(85), dp(85)),
            allow_stretch=True
        )
        
        # Text label
        self.logo_text = Label(
            text="Kaibu",
            font_size=dp(35),
            font_name='Qilka-Bold',
            color=hex_to_rgb("#F6CBB6"),
            size_hint=(None, None),
            size=(dp(100), dp(75))
        )

        self.add_widget(self.logo_img)
        self.add_widget(self.logo_text)
        
        # Calculate width based on contents
        self.width = self.logo_img.width + self.logo_text.width + self.spacing

class PauseContinueButton(Button):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Disable default button background
        self.background_normal = ''
        self.background_down = ''
        self.background_color = (0, 0, 0, 0)  # Transparent background
        
        # Set the size of the button
        self.size_hint = (None, None)
        self.size = (dp(75), dp(75))
        
        # Initial state (playing)
        self.is_paused = False
        self.update_icon()
        
        # Bind the click event
        self.bind(on_press=self.toggle_state)

    def update_icon(self):
        with self.canvas:
            self.canvas.clear()
            Color(1, 1, 1, 1)  # No tint
            # Use pause or play icon based on state
            icon = 'Pictures/pause.png' if not self.is_paused else 'Pictures/play.png'
            self.rect = Rectangle(source=icon, pos=self.pos, size=self.size)
        
        # Update the rectangle when position changes
        self.bind(pos=self._update_rect, size=self._update_rect)

    def _update_rect(self, *args):
        if hasattr(self, 'rect'):
            self.rect.pos = self.pos
            self.rect.size = self.size

    def toggle_state(self, instance):
        self.is_paused = not self.is_paused
        self.update_icon()
        
        # Update the global recording state
        global recording_active
        recording_active = not self.is_paused
        
        if self.is_paused:
            print("Conversation paused - microphone off")
        else:
            print("Conversation resumed - microphone on")

# Splash Screen
class SplashScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.layout = FloatLayout()
        self.add_widget(self.layout)

        # Centered Kaibu Logo (replaces the circle)
        self.logo = Image(
            source='Pictures/Kaibu_Logo.png',  # Make sure the image is in your project folder
            size_hint=(None, None),
            size=(dp(300), dp(300)),  # Adjust size as needed
            pos_hint={'center_x': 0.5, 'center_y': 0.5},
            allow_stretch=True,
            keep_ratio=True
        )
        self.layout.add_widget(self.logo)

        # Click to Start Label
        self.start_label = Label(
            text="Click anywhere to start",
            size_hint=(1, None),
            height=dp(50),
            valign='middle',
            halign='center',
            font_size=dp(18),
            font_name='Qilka-Bold',
            color=hex_to_rgb("#F6CBB6"),
            pos_hint={'center_x': 0.5, 'y': 0}
        )
        self.layout.add_widget(self.start_label)

        # Bind click
        self.bind(on_touch_down=self.switch_screen)

    def switch_screen(self, *args):
        self.manager.current = 'conversation'

# Farewell Popup
class FarewellPopup(Popup):
    def __init__(self, duration, **kwargs):
        super().__init__(**kwargs)
        self.title = 'Meal Complete!'
        self.size_hint = (0.8, 0.5)
        self.auto_dismiss = False
        
        # Main layout with padding
        layout = BoxLayout(
            orientation='vertical',
            spacing=dp(10),
            padding=dp(20),
            size_hint=(1, 1)
        )
        
        # Calculate duration
        minutes = int(duration // 60)
        seconds = int(duration % 60)
        duration_text = f"{minutes} minutes and {seconds} seconds"
        
        # Message label with dynamic sizing
        message = Label(
            text=f"You spent {duration_text} enjoying your meal!",
            font_size=dp(18),
            halign='center',
            valign='middle',
            size_hint_y=None,
            text_size=(None, None),  # Will be set in update_text_size
            padding=(dp(10), dp(10))
        )
        
        # Function to update text size based on popup width
        def update_text_size(instance, value):
            # Calculate max width (popup width minus padding)
            max_width = self.width * 0.9  # 90% of popup width
            message.text_size = (max_width, None)
            message.height = message.texture_size[1] + dp(20)  # Add some padding
            
        # Bind to size changes
        self.bind(width=update_text_size)
        
        # Return button
        button = Button(
            text="Return to Home",
            size_hint_y=None,
            height=dp(50),
            background_normal='',
            background_color=hex_to_rgb("#F6CBB6"),
            color=hex_to_rgb("#472950")
        )
        button.bind(on_press=self.dismiss)
        
        # Add widgets with appropriate proportions
        layout.add_widget(message)
        layout.add_widget(Widget(size_hint_y=0.1))  # Spacer
        layout.add_widget(button)
        
        self.content = layout
        
        # Initial size update
        Clock.schedule_once(lambda dt: update_text_size(None, None))

# Conversation Screen
class ConversationScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.conversation_history = []  # Store conversation history as instance variable
        self.message_list = []  # Store messages for display
        self.running = False  # Flag to control conversation loop
        self.recording_indicator = None  # To track the recording indicator message
        self.last_user_message = None  # To store the last user message before pause

        with self.canvas.before:
            Color(*hex_to_rgb("#472950"))  # Conversation screen background
            self.bg_rect = Rectangle(size=self.size, pos=self.pos)
        self.bind(size=self._update_bg, pos=self._update_bg)

        self.layout = BoxLayout(orientation='vertical')

        # Header
        self.header = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(100),
            padding=[dp(10), dp(10), dp(10), dp(10)]
        )
        with self.header.canvas.before:
            Color(*hex_to_rgb("#7e6984"))  # Header background
            self.header_rect = Rectangle(pos=self.header.pos, size=self.header.size)
        self.header.bind(pos=self._update_header_rect, size=self._update_header_rect)

        # Mini Logo with text
        self.mini_logo = MiniLogo()
        self.header.add_widget(self.mini_logo)

        # Spacer to push buttons to the right
        self.header.add_widget(Widget(size_hint_x=1))

        # Pause/Continue Button
        self.pause_btn = PauseContinueButton()
        self.header.add_widget(self.pause_btn)

        # Finish Button
        self.finish_btn = FinishButton()
        self.finish_btn.bind(on_press=self.switch_to_splash)
        self.header.add_widget(self.finish_btn)

        self.layout.add_widget(self.header)

        # Scrollable Conversation Area
        self.scroll = ScrollView(
            size_hint=(1, 1),
            bar_width=dp(10),
            bar_inactive_color=(0.8, 0.8, 0.8, 1),
            bar_color=(0.5, 0.5, 0.5, 1)
        )

        self.convo_layout = BoxLayout(
            orientation='vertical',
            spacing=dp(10),
            padding=[dp(15), dp(10), dp(15), dp(10)],
            size_hint_y=None
        )
        self.convo_layout.bind(minimum_height=self.convo_layout.setter('height'))

        self.scroll.add_widget(self.convo_layout)
        self.layout.add_widget(self.scroll)
        self.add_widget(self.layout)

    def on_enter(self):
        """Called every time the screen comes into view"""
        if not self.running:
            self.running = True
            welcome_msg = "Hi there! I'm ready to chat with you during your meal. What are you eating today?"
            self.add_message("Kaibu", welcome_msg)
            Clock.schedule_once(lambda dt: run_tts(welcome_msg), 0.1)
            Clock.schedule_once(lambda dt: self.start_conversation(), 0.5)

    def on_leave(self):
        """Called when leaving the screen"""
        self.running = False

    def start_conversation(self):
        """Start the conversation loop in a separate thread"""
        import threading
        threading.Thread(target=self.conversation_loop, daemon=True).start()

    def conversation_loop(self):
        """The main conversation loop"""
        error_count = 0
        conversation_generated = True  # Flag to track if conversation is fully generated
        
        while self.running:
            try:
                # Check if we should stop immediately
                if not self.running:
                    break
                
                # Wait for both TTS and conversation generation to complete
                if self.pause_btn.is_paused:
                    conversation_generated = True  # Set this to prevent response generation
                    time.sleep(0.1)
                    continue
                
                if conversation_generated == True:
                    time.sleep(0.3)

                while True:
                    # Check if we should stop
                    if not self.running:
                        return
                        

                    with tts_lock:
                        if not ai_speaking and conversation_generated:
                            break
                    time.sleep(0.1)
                    if ai_speaking:
                        print("Waiting for TTS to finish...")
                    else:
                        print("Waiting for conversation generation...")
                        
                # Check again before continuing
                if not self.running:
                    break
                
                # Reset conversation flag for new interaction
                conversation_generated = False
                
                # Skip listening if paused
                if self.pause_btn.is_paused:
                    time.sleep(0.5)
                    continue
                
                # Check one more time before listening
                if not self.running:
                    break
                
                audio = listen_with_feedback()
                
                # Check if we should stop after getting audio
                if not self.running:
                    break
                
                if audio is None:
                    continue
                
                try:
                    text = r.recognize_google(audio)
                    print(f"\nYou said: {text}")
                    Clock.schedule_once(lambda dt: self.add_message("User", text))
                    error_count = 0
                    
                    if any(phrase in text.lower() for phrase in ["stop listening", "exit", "quit", "goodbye", "bye", "see you"]):
                        elapsed_minutes = (time.time() - meal_info["start_time"]) / 60
                        farewell_message = f"Thanks for letting me keep you company for {elapsed_minutes:.1f} minutes! Hope you enjoyed your meal!"
                        Clock.schedule_once(lambda dt: self.add_message("Kaibu", farewell_message))
                        conversation_generated = True  # Mark as generated before TTS
                        Clock.schedule_once(lambda dt: run_tts(farewell_message, lambda: self.show_farewell_popup()), 0.1)
                        self.running = False
                        return
                    
                    self.conversation_history.append({"role": "user", "content": text})
                    
                    if len(self.conversation_history) > 6:
                        self.conversation_history = self.conversation_history[-6:]
                    
                    messages = [
                        {"role": "system", "content": get_dynamic_personality()}
                    ] + self.conversation_history
                    
                    show_status("Thinking...", "")
                    try:
                        response = client.chat.completions.create(
                            model="openai/gpt-3.5-turbo",
                            messages=messages,
                            temperature=0.9,
                            max_tokens=150
                        )
                        
                        ai_response = response.choices[0].message.content
                        self.conversation_history.append({"role": "assistant", "content": ai_response})
                        
                        print("\n" + "="*50)
                        print(f"Kaibu: {ai_response}")
                        print("="*50)
                        
                        # Update UI from main thread
                        Clock.schedule_once(lambda dt: self.add_message("Kaibu", ai_response))
                        
                        # Mark conversation as generated
                        conversation_generated = True
                        
                        # Run TTS with a callback when done
                        def tts_done():
                            print("TTS finished speaking")
                        
                        # Start TTS only after conversation is marked as generated
                        Clock.schedule_once(lambda dt: run_tts(ai_response, tts_done), 0.1)
                        
                    except Exception as api_error:
                        error_response = f"Sorry, I'm having trouble thinking right now. API Error: {api_error}"
                        print(f"{error_response}")
                        
                        fallback_response = "Sorry, I'm having a little brain fog right now! But I'm still here with you. What were you saying about your meal?"
                        Clock.schedule_once(lambda dt: self.add_message("Kaibu", fallback_response))
                        conversation_generated = True  # Mark as generated before TTS
                        Clock.schedule_once(lambda dt: run_tts(fallback_response), 0.1)
                    
                except sr.UnknownValueError:
                    error_count += 1
                    error_message = handle_recognition_error(error_count)
                    conversation_generated = True 
                    print(error_message)
                    if error_count >= 3:
                        recalibrate_msg = "Let me recalibrate my ears..."
                        print("Recalibrating microphone...")
                        with microphone as source:
                            r.adjust_for_ambient_noise(source, duration=1)
                        error_count = 0
                        
                except sr.RequestError as e:
                    conversation_generated = True
                    error_msg = "Oops! Speech recognition service error. Let me try to recalibrate..."
                    print(f"{error_msg}")
                    with microphone as source:
                        r.adjust_for_ambient_noise(source, duration=1)
                    
            except KeyboardInterrupt:
                elapsed_minutes = (time.time() - meal_info["start_time"]) / 60
                farewell_message = f"Chat ended after {elapsed_minutes:.1f} minutes. Hope you enjoyed your meal!"
                print(f"\n{farewell_message}")
                Clock.schedule_once(lambda dt: self.add_message("Kaibu", farewell_message))
                conversation_generated = True  # Mark as generated before TTS
                Clock.schedule_once(lambda dt: run_tts(farewell_message, lambda: self.show_farewell_popup()), 0.1)
                self.running = False
                return
            except Exception as e:
                print(f"Something went wrong: {e}")
                print("But I'm still here! Try speaking again.")
                
                try:
                    with microphone as source:
                        r.adjust_for_ambient_noise(source, duration=1)
                except:
                    pass

    def remove_recording_indicator(self):
        """Remove the recording indicator if it exists"""
        if self.recording_indicator:
            # Find and remove the recording indicator from the conversation layout
            for widget in self.convo_layout.children[:]:
                if hasattr(widget, 'is_temporary') and widget.is_temporary:
                    self.convo_layout.remove_widget(widget)
            self.recording_indicator = None

    def show_farewell_popup(self):
        """Show the farewell popup with meal duration"""
        duration = time.time() - meal_info["start_time"]
        popup = FarewellPopup(duration=duration)
        popup.bind(on_dismiss=self._final_switch)
        popup.open()

    def _update_bg(self, *args):
        self.bg_rect.size = self.size
        self.bg_rect.pos = self.pos

    def _update_header_rect(self, *args):
        self.header_rect.pos = self.header.pos
        self.header_rect.size = self.header.size

    def end_mealtime(self):
        """End the mealtime conversation and show farewell"""
        # Stop the conversation loop immediately
        self.running = False
        
        # Stop any ongoing TTS
        global ai_speaking
        with tts_lock:
            ai_speaking = False
        
        # Calculate elapsed time and create farewell message
        elapsed_minutes = (time.time() - meal_info["start_time"]) / 60
        farewell_message = f"Thanks for letting me keep you company for {elapsed_minutes:.1f} minutes! Hope you enjoyed your meal!"
        
        # Add farewell message to conversation
        Clock.schedule_once(lambda dt: self.add_message("Kaibu", farewell_message))
        
        # Speak the farewell message and show popup when done
        Clock.schedule_once(lambda dt: run_tts(farewell_message, lambda: self.show_farewell_popup()), 0.1)

    def switch_to_splash(self, *args):
        """Handler for the finish button - ends mealtime"""
        self.end_mealtime()

    def _final_switch(self, *args):
        """Final switch to splash screen after popup is dismissed"""
        # Reset conversation state
        self.reset_conversation_state()
        # Navigate to splash screen
        self.manager.current = 'splash'

    def reset_conversation_state(self):
        """Resets the conversation history, UI messages, and related state."""
        global meal_info
        
        # Clear conversation history
        self.conversation_history = []
        self.message_list = []
        
        # Clear UI message bubbles
        self.convo_layout.clear_widgets()
        
        # Reset meal timer
        meal_info = {
            "start_time": time.time(),
            "topics_discussed": [],
            "mood": "neutral"
        }

    def add_message(self, sender, text, temporary=False):
        """Add a new message and display it"""
        message = Message(sender, text)
        if not temporary:
            self.message_list.append(message)
        self.display_message(sender, text, temporary)

    def display_message(self, sender, text, temporary=False):
        """Display a message"""
        is_user = sender == "User"

        # Label for the message text
        label = Label(
            text=text,
            size_hint=(None, None),
            font_size=dp(16),
            halign='left',
            valign='middle',
            color=(1, 1, 1, 1),  # White text
            padding=[dp(10), dp(10)],  
            text_size=(None, None)
        )

        # Bubble layout
        bubble = BoxLayout(
            orientation='vertical',
            size_hint=(None, None),
            padding=[0, 0]
        )
        bubble.is_temporary = temporary  # Mark temporary messages

        bubble_color = hex_to_rgb("#C0A4C4") if not is_user else hex_to_rgb("#D46A79")

        # Background rectangle for the bubble
        with bubble.canvas.before:
            Color(*bubble_color)
            bg_rect = RoundedRectangle(pos=bubble.pos, size=bubble.size, radius=[10, 10, 10, 10])

        # Update bubble background position and size
        bubble.bind(pos=lambda instance, value: setattr(bg_rect, 'pos', value))
        bubble.bind(size=lambda instance, value: setattr(bg_rect, 'size', value))

        # Add label to bubble
        bubble.add_widget(label)

        # Container layout to align bubble left or right
        box = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(40)
        )

        if is_user:
            box.add_widget(BoxLayout(size_hint_x=0.2))  # Left spacer
            box.add_widget(bubble)
        else:
            box.add_widget(bubble)
            box.add_widget(BoxLayout(size_hint_x=0.2))  # Right spacer

        self.convo_layout.add_widget(box)

        # Function to update bubble size and wrapping
        def update_message_width(*args):
            max_width = Window.width * 0.7  # Max bubble width is 60% of screen width

            # First, calculate natural width of text
            label.text_size = (None, None)  # No wrapping at first
            label.texture_update()
            natural_width = label.texture_size[0]

            # Now decide: if natural width > max_width, wrap text
            effective_width = min(natural_width, max_width)
            label.text_size = (effective_width, None)

            # Update again with wrapping applied
            label.texture_update()
            label.width = label.texture_size[0]
            label.height = label.texture_size[1]

            bubble.width = label.width
            bubble.height = label.height
            box.height = bubble.height

        # Initial update
        update_message_width()

        # Bind to window resize
        Window.bind(on_resize=update_message_width)

        # Scroll to bottom after adding message
        Clock.schedule_once(lambda dt: self.scroll_to_bottom(), 0.1)

    def scroll_to_bottom(self):
        """Scroll the conversation to the bottom"""
        if self.scroll:
            self.scroll.scroll_y = 0

# App Setup
class MealtimeApp(App):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(SplashScreen(name='splash'))
        sm.add_widget(ConversationScreen(name='conversation'))
        return sm

if __name__ == '__main__':
    MealtimeApp().run()
