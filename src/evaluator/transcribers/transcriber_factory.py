"""
Factory module for creating transcriber instances.
"""
from typing import Dict, Type, Any, List
from .abstract_transcriber import AbstractTranscriber


class TranscriberFactory:
    """
    Factory class to create and manage transcriber instances.
    """
    _transcribers: Dict[str, Type[AbstractTranscriber]] = {}

    @staticmethod
    def register(name: str, transcriber_cls: Type[AbstractTranscriber]) -> None:
        """
        Registers a transcriber class under a specific name.

        Args:
            name (str): The name to register the transcriber under.
            transcriber_cls (Type[AbstractTranscriber]): The transcriber class.
        """
        TranscriberFactory._transcribers[name] = transcriber_cls

    @staticmethod
    def get_transcriber(name: str, **kwargs: Any) -> AbstractTranscriber:
        """
        Returns an instance of the specified transcriber.

        Args:
            name (str): The name of the transcriber to instantiate.
            **kwargs: Additional arguments to pass to the transcriber constructor.

        Returns:
            AbstractTranscriber: An instance of the requested transcriber.

        Raises:
            ValueError: If the transcriber name is not registered.
        """
        transcriber_cls = TranscriberFactory._transcribers.get(name)
        if not transcriber_cls:
            available = ", ".join(TranscriberFactory._transcribers.keys())
            raise ValueError(
                f"Transcriber '{name}' is not registered. Available: {available}")

        return transcriber_cls(**kwargs)

    @staticmethod
    def list_transcribers() -> List[str]:
        """
        Returns a list of registered transcriber names.

        Returns:
            List[str]: A list of names.
        """
        return list(TranscriberFactory._transcribers.keys())
