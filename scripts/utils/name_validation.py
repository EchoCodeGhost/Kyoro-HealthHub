#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
name_validation — Generisches Namensvalidierungs- und Erkennungsmodul

@tier        infrastructure
@purpose.de  Bietet Funktionen zur Erkennung und Validierung von Namen unter Verwendung der
              Konfiguration aus name_lists.json.Arbeitet mit dem Pseudonymisierungssystem zusammen,
              um potenziell persönliche Informationen in Textdaten zu identifizieren.
              Hauptfunktionen: Erkennung häufiger deutscher Vor- und Nachnamen,
              Identifizierung von Namensmustern (z.B. "Vorname Nachname"), Validierung von Namensformaten,
              Integration mit dem Pseudonymisierungssystem.
@purpose.en  Provides functions to detect and validate names using configuration from
              name_lists.json. Works alongside the pseudonymization system to identify potential
              personal information in text data.
              Key features: Detect common German first and last names,
              identify name patterns (e.g., "Firstname Lastname"), validate name formats,
              integrate with pseudonymization system.
@method.de   Lädt Namenslisten aus name_lists.json im utils/ Verzeichnis oder verwendet
              eingebaute Fallback-Listen. Nutzt reguläre Ausdrücke für effiziente Mustererkennung.
              Die NameDetector-Klasse bietet Methoden für: Einzelne Vor-/Nachnamen prüfen,
              Vollständige Namen erkennen, Titel+Name-Kombinationen erkennen,
              umfassende Namenserkennung in Texten, person_id-Validierung.
              Ein Singleton-Objekt (detector) wird für einfache Nutzung bereitgestellt.
@method.en   Loads name lists from name_lists.json in utils/ directory or uses built-in
              fallback lists. Uses regular expressions for efficient pattern matching.
              The NameDetector class provides methods for: checking individual first/last names,
              detecting full names, detecting title+name combinations,
              comprehensive name detection in texts, person_id validation.
              A singleton object (detector) is provided for easy use.
@reads       scripts/utils/name_lists/name_lists.json
@writes      (keine Schreiboperationen)
@limits.de   Erkennt nur in den Namenslisten konfigurierte Namen.
              Case-insensitive Vergleich für bessere Trefferquote.
              Verarbeitet keine echten Personendaten - dient nur der Erkennung von Mustern.

@relevance.de  Bietet Hilfsfunktionen für die Datenverarbeitung, essentiell für die Systemfunktionalität
@relevance.en  Provides utility functions for data processing, essential for system functionality
@limits.en   Only detects names configured in the name lists.
              Case-insensitive comparison for better match rate.
              Does not process real personal data - only used for pattern detection.
@usage
    from utils.name_validation import NameDetector, is_common_first_name, detect_names_in_text
    detector = NameDetector()
    # Einzelne Namen prüfen
    is_first = is_common_first_name("Anna")
    is_last = is_common_last_name("Müller")
    # Umfassende Erkennung in Text
    names = detect_names_in_text("Dr. med. Anna Müller war hier")
    # Person-ID validieren
    valid = detector.validate_person_id("user_123")
"""

import re
from typing import Tuple
from .anonymize import _load_name_lists


class NameDetector:
    """Main class for name detection and validation."""
    
    def __init__(self):
        """Initialize with name lists from configuration."""
        self.name_lists = _load_name_lists()
        # Store names in lowercase for case-insensitive comparison
        self.first_names = set(name.lower() for name in self.name_lists["common_first_names"])
        self.last_names = set(name.lower() for name in self.name_lists["common_last_names"])
        self.arzt_titles = set(self.name_lists["common_arzt_titles"])
        self.mvz_patterns = self.name_lists["common_mvz_names"]
        
        # Compile regex patterns for efficiency
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compile regular expression patterns for name detection."""
        # Pattern for "Firstname Lastname" (case insensitive)
        first_name_pattern = r'\b(' + '|'.join(map(re.escape, self.first_names)) + r')\b'
        last_name_pattern = r'\b(' + '|'.join(map(re.escape, self.last_names)) + r')\b'
        
        # Full name pattern (first + last name)
        self.full_name_pattern = re.compile(
            rf'{first_name_pattern}\s+{last_name_pattern}',
            flags=re.IGNORECASE
        )
        
        # Title + name pattern (e.g., "Dr. med. Müller")
        # Need to handle titles carefully - some contain regex special characters
        # Sort titles by length (longest first) to avoid partial matches
        sorted_titles = sorted(self.arzt_titles, key=len, reverse=True)
        title_patterns = []
        for title in sorted_titles:
            # Escape regex special characters but preserve the structure
            escaped_title = re.escape(title)
            # Replace escaped spaces with literal spaces for better matching
            escaped_title = escaped_title.replace(r'\ ', ' ')
            title_patterns.append(escaped_title)
        
        title_pattern = r'\b(' + '|'.join(title_patterns) + r')'
        # Use \s+ for the space between title and last name, but don't require word boundary after title
        # since titles like "Dr. med." already end with punctuation
        self.title_name_pattern = re.compile(
            rf'{title_pattern}\s+{last_name_pattern}',
            flags=re.IGNORECASE
        )
        
        # Single first name pattern
        self.single_first_name_pattern = re.compile(first_name_pattern, flags=re.IGNORECASE)
        
        # Single last name pattern
        self.single_last_name_pattern = re.compile(last_name_pattern, flags=re.IGNORECASE)
    
    def is_common_first_name(self, name: str) -> bool:
        """Check if a given string is a common German first name."""
        if not name or not isinstance(name, str):
            return False
        return name.lower() in self.first_names
    
    def is_common_last_name(self, name: str) -> bool:
        """Check if a given string is a common German last name."""
        if not name or not isinstance(name, str):
            return False
        return name.lower() in self.last_names
    
    def detect_full_names(self, text: str) -> list[Tuple[str, str, str]]:
        """
        Detect full name patterns (Firstname Lastname) in text.
        
        Returns list of tuples: (full_match, first_name, last_name)
        """
        if not text or not isinstance(text, str):
            return []
            
        matches = []
        for match in self.full_name_pattern.finditer(text):
            full_match = match.group(0)
            first_name = match.group(1)
            last_name = match.group(2)
            matches.append((full_match, first_name, last_name))
        
        return matches
    
    def detect_title_names(self, text: str) -> list[Tuple[str, str, str]]:
        """
        Detect title + name patterns (e.g., "Dr. med. Müller") in text.
        
        Returns list of tuples: (full_match, title, last_name)
        """
        if not text or not isinstance(text, str):
            return []
            
        matches = []
        for match in self.title_name_pattern.finditer(text):
            full_match = match.group(0)
            title = match.group(1)
            last_name = match.group(2)
            matches.append((full_match, title, last_name))
        
        return matches
    
    def detect_any_names(self, text: str) -> dict:
        """
        Comprehensive name detection in text.
        
        Returns a dictionary with all detected name types:
        {
            'full_names': [(full_match, first, last), ...],
            'title_names': [(full_match, title, last), ...],
            'single_first': [first_name, ...],
            'single_last': [last_name, ...]
        }
        """
        if not text or not isinstance(text, str):
            return {'full_names': [], 'title_names': [], 'single_first': [], 'single_last': []}
        
        # Find full names
        full_names = self.detect_full_names(text)
        
        # Find title + name combinations
        title_names = self.detect_title_names(text)
        
        # Find single first names (not part of full names)
        single_first = []
        used_positions = set()
        
        # Mark positions used by full names to avoid duplicates
        for full_match, _, _ in full_names:
            start = text.lower().find(full_match.lower())
            if start != -1:
                used_positions.add((start, start + len(full_match)))
        
        # Find single first names not in used positions
        for match in self.single_first_name_pattern.finditer(text):
            match_start, match_end = match.span()
            is_used = False
            
            # Check if this match overlaps with any full name
            for (full_start, full_end) in used_positions:
                if not (match_end <= full_start or match_start >= full_end):
                    is_used = True
                    break
            
            if not is_used:
                single_first.append(match.group(0))
        
        # Find single last names (not part of full names or title names)
        single_last = []
        
        # Mark positions used by title names
        for full_match, _, _ in title_names:
            start = text.lower().find(full_match.lower())
            if start != -1:
                used_positions.add((start, start + len(full_match)))
        
        # Find single last names not in used positions
        for match in self.single_last_name_pattern.finditer(text):
            match_start, match_end = match.span()
            is_used = False
            
            # Check if this match overlaps with any used position
            for (full_start, full_end) in used_positions:
                if not (match_end <= full_start or match_start >= full_end):
                    is_used = True
                    break
            
            if not is_used:
                single_last.append(match.group(0))
        
        return {
            'full_names': full_names,
            'title_names': title_names,
            'single_first': single_first,
            'single_last': single_last
        }
    
    def validate_person_id(self, person_id: str) -> bool:
        """
        Validate that a person_id doesn't contain obvious personal names.
        
        Returns True if the person_id looks safe (no obvious names),
        False if it contains potential personal information.
        """
        if not person_id or not isinstance(person_id, str):
            return True
            
        # Check for spaces (indicates multiple words, like "First Last")
        if ' ' in person_id.strip():
            return False
            
        # Check for @ symbol (email address)
        if '@' in person_id:
            return False
            
        # Check if it's a common first or last name
        person_id_lower = person_id.strip().lower()
        if (person_id_lower in self.first_names or 
            person_id_lower in self.last_names):
            return False
            
        return True
    
    def contains_potential_names(self, text: str) -> bool:
        """Quick check if text contains any potential names."""
        detection = self.detect_any_names(text)
        return (len(detection['full_names']) > 0 or 
                len(detection['title_names']) > 0 or
                len(detection['single_first']) > 0 or
                len(detection['single_last']) > 0)


# Singleton instance for convenience
detector = NameDetector()


def is_common_first_name(name: str) -> bool:
    """Convenience function to check if a string is a common first name."""
    return detector.is_common_first_name(name)


def is_common_last_name(name: str) -> bool:
    """Convenience function to check if a string is a common last name."""
    return detector.is_common_last_name(name)


def detect_names_in_text(text: str) -> dict:
    """Convenience function for comprehensive name detection."""
    return detector.detect_any_names(text)


def validate_person_id(person_id: str) -> bool:
    """Convenience function to validate a person_id."""
    return detector.validate_person_id(person_id)


def contains_potential_names(text: str) -> bool:
    """Convenience function to check for any potential names in text."""
    return detector.contains_potential_names(text)