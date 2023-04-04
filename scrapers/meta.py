import threading


class Singleton(type):
    """
    Singleton metaclass for classes that should only have one instance.
    """
    
    __instance = {}
    __lock = threading.Lock()
    
    def __call__(cls, *args, **kwargs):
        if cls not in cls.__instance:
            with cls.__lock:
                if cls not in cls.__instance:
                    cls.__instance[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls.__instance[cls]