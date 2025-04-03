"""
Třída pro barevnou korekci obrázků.
Poskytuje možnost úpravy jasu, kontrastu, sytosti a gamma korekce.
"""

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
from dataclasses import dataclass
from typing import Optional, Tuple

@dataclass
class ColorCorrection:
    """
    Třída pro barevnou korekci obrázků.
    
    Atributy:
        brightness (float): Hodnota jasu (1.0 = beze změny, <1.0 = tmavší, >1.0 = světlejší)
        contrast (float): Hodnota kontrastu (1.0 = beze změny, <1.0 = méně kontrastu, >1.0 = více kontrastu)
        saturation (float): Hodnota sytosti (1.0 = beze změny, <1.0 = méně sytosti, >1.0 = více sytosti)
        gamma (float): Hodnota gamma korekce (1.0 = beze změny, <1.0 = světlejší střední tóny, >1.0 = tmavší střední tóny)
        sharpen (float): Hodnota doostření (0.0 = beze změny, >0.0 = více ostrosti)
    """
    brightness: float = 1.0
    contrast: float = 1.0
    saturation: float = 1.0
    gamma: float = 1.0
    sharpen: float = 0.0
    
    def __post_init__(self):
        """Validace hodnot po inicializaci"""
        if self.brightness <= 0:
            raise ValueError("Hodnota jasu musí být větší než 0")
        if self.contrast <= 0:
            raise ValueError("Hodnota kontrastu musí být větší než 0")
        if self.saturation <= 0:
            raise ValueError("Hodnota sytosti musí být větší než 0")
        if self.gamma <= 0:
            raise ValueError("Hodnota gamma korekce musí být větší než 0")
        if self.sharpen < 0:
            raise ValueError("Hodnota doostření musí být větší nebo rovna 0")
    
    def apply_to_image(self, image: Image.Image) -> Image.Image:
        """
        Aplikuje barevnou korekci na obrázek.
        
        Args:
            image: PIL Image objekt
            
        Returns:
            PIL Image objekt s aplikovanou barevnou korekcí
        """
        # Vytvoříme kopii obrázku, abychom nemodifikovali originál
        img = image.copy()
        
        # Zjistíme, zda má obrázek alfa kanál
        has_alpha = img.mode == 'RGBA'
        
        # Pokud má obrázek alfa kanál, oddělíme ho
        if has_alpha:
            # Rozdělíme obrázek na RGB a alfa kanál
            rgb_img = img.convert('RGB')
            alpha = img.split()[3]
        else:
            rgb_img = img
        
        # Aplikace jasu
        if self.brightness != 1.0:
            enhancer = ImageEnhance.Brightness(rgb_img)
            rgb_img = enhancer.enhance(self.brightness)
        
        # Aplikace kontrastu
        if self.contrast != 1.0:
            enhancer = ImageEnhance.Contrast(rgb_img)
            rgb_img = enhancer.enhance(self.contrast)
        
        # Aplikace sytosti
        if self.saturation != 1.0:
            enhancer = ImageEnhance.Color(rgb_img)
            rgb_img = enhancer.enhance(self.saturation)
        
        # Aplikace gamma korekce
        if self.gamma != 1.0:
            # Převedeme obrázek na numpy array
            img_array = np.array(rgb_img).astype(np.float32) / 255.0
            
            # Aplikujeme gamma korekci
            img_array = np.power(img_array, 1.0 / self.gamma)
            
            # Převedeme zpět na rozsah 0-255 a uint8
            img_array = np.clip(img_array * 255.0, 0, 255).astype(np.uint8)
            
            # Vytvoříme nový PIL Image
            rgb_img = Image.fromarray(img_array)
        
        # Aplikace doostření
        if self.sharpen > 0:
            # Vytvoříme masku doostření
            blurred = rgb_img.filter(ImageFilter.GaussianBlur(radius=2))
            mask = ImageEnhance.Brightness(rgb_img).enhance(1.0 + self.sharpen)
            mask = ImageEnhance.Contrast(mask).enhance(1.0 + self.sharpen)
            
            # Aplikujeme masku doostření
            rgb_img = Image.blend(blurred, mask, self.sharpen)
        
        # Pokud měl původní obrázek alfa kanál, přidáme ho zpět
        if has_alpha:
            # Převedeme RGB obrázek zpět na RGBA a přidáme původní alfa kanál
            r, g, b = rgb_img.split()
            rgb_img = Image.merge('RGBA', (r, g, b, alpha))
        
        return rgb_img
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ColorCorrection':
        """
        Vytvoří instanci ColorCorrection z dictionary.
        
        Args:
            data: Dictionary s hodnotami pro barevnou korekci
            
        Returns:
            Instance ColorCorrection
        """
        return cls(
            brightness=data.get('brightness', 1.0),
            contrast=data.get('contrast', 1.0),
            saturation=data.get('saturation', 1.0),
            gamma=data.get('gamma', 1.0),
            sharpen=data.get('sharpen', 0.0)
        )
    
    def to_dict(self) -> dict:
        """
        Převede instanci ColorCorrection na dictionary.
        
        Returns:
            Dictionary s hodnotami pro barevnou korekci
        """
        return {
            'brightness': self.brightness,
            'contrast': self.contrast,
            'saturation': self.saturation,
            'gamma': self.gamma,
            'sharpen': self.sharpen
        }
    
    def is_identity(self) -> bool:
        """
        Zjistí, zda je barevná korekce identická (nemění obrázek).
        
        Returns:
            True, pokud barevná korekce nemění obrázek, jinak False
        """
        return (self.brightness == 1.0 and 
                self.contrast == 1.0 and 
                self.saturation == 1.0 and 
                self.gamma == 1.0 and 
                self.sharpen == 0.0)