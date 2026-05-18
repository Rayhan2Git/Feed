import { useState, useEffect, useRef, useCallback } from 'react';
import { Search, Play, X, ChevronLeft, ChevronRight, Home, Clock, Flame, Volume2, VolumeX, Maximize, SkipBack, SkipForward, ArrowLeft, Instagram, Heart, Bookmark, Grid } from 'lucide-react';
import useEmblaCarousel from 'embla-carousel-react';
import { parseM3U, filterVideosBySearch, type CategoryVideos, type Video } from '@/lib/m3uParser';

const M3U_URL = 'https://raw.githubusercontent.com/Rayhan2Git/Feed/main/playlist.m3u';

function formatTime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

// Shuffle array function (Fisher-Yates)
function shuffleArray<T>(array: T[]): T[] {
  const shuffled = [...array];
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
  }
  return shuffled;
}

// Optimized TikTok-style Vertical Player - Only 1 video loads at a time
function TikTokPlayer({ videos, onClose, favorites, onToggleFavorite, onShowFavorites, startVideo }: {
  videos: Video[];
  onClose: () => void;
  favorites: Video[];
  onToggleFavorite: (video: Video) => void;
  onShowFavorites: () => void;
  startVideo?: Video;
}) {
  // Shuffle videos on initial load for random order
  const shuffledVideos = useRef(shuffleArray(videos)).current;
  const [currentIndex, setCurrentIndex] = useState(() => {
    if (startVideo) {
      const idx = shuffledVideos.findIndex(v => v.id === startVideo.id);
      return idx >= 0 ? idx : 0;
    }
    return 0;
  });
  const [isMuted, setIsMuted] = useState(true);
  const [isAutoScroll, setIsAutoScroll] = useState(false);
  const [isPlaying, setIsPlaying] = useState(true);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const [slideDirection, setSlideDirection] = useState<'up' | 'down' | null>(null);
  const [touchStart, setTouchStart] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const videoRef = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const preloadRef = useRef<HTMLVideoElement>(null); // Preload next video
  const currentVideo = shuffledVideos[currentIndex];
  const nextVideo = shuffledVideos[currentIndex + 1];
  const autoScrollRef = useRef<NodeJS.Timeout>();
  const videoList = shuffledVideos;
  const isFavorite = currentVideo ? favorites.some(v => v.id === currentVideo.id) : false;

  // Preload next video when current video starts playing
  useEffect(() => {
    const video = videoRef.current;
    if (!video || !nextVideo) return;

    const handlePlaying = () => {
      if (preloadRef.current && nextVideo) {
        preloadRef.current.src = nextVideo.url;
        preloadRef.current.load();
      }
    };

    video.addEventListener('playing', handlePlaying);
    return () => video.removeEventListener('playing', handlePlaying);
  }, [nextVideo]);

  // Clear video source when changing
  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.src = '';
      videoRef.current.load();
    }
  }, []);

  // Load new video when index changes (use preloaded if available)
  useEffect(() => {
    const loadVideo = async () => {
      if (videoRef.current && currentVideo) {
        // First check if the current video is already preloaded
        if (preloadRef.current && preloadRef.current.src.includes(encodeURIComponent(currentVideo.url))) {
          // Swap the preloaded video to main
          const tempSrc = videoRef.current.src;
          videoRef.current.src = preloadRef.current.src;
          preloadRef.current.src = tempSrc;
          videoRef.current.load();
          videoRef.current.muted = isMuted;
        } else {
          videoRef.current.src = currentVideo.url;
          videoRef.current.load();
          videoRef.current.muted = isMuted;
        }
      }
    };
    loadVideo();
  }, [currentIndex, currentVideo]);

  // Play video when loaded
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const handleCanPlay = () => {
      if (isPlaying && !isTransitioning) {
        video.play().catch(() => {});
      }
    };

    video.addEventListener('canplay', handleCanPlay);
    return () => video.removeEventListener('canplay', handleCanPlay);
  }, [isPlaying, isTransitioning, currentVideo]);

  // Auto-scroll effect
  useEffect(() => {
    if (autoScrollRef.current) {
      clearInterval(autoScrollRef.current);
      autoScrollRef.current = undefined;
    }

    if (isAutoScroll) {
      autoScrollRef.current = setInterval(() => {
        goToNext();
      }, 8000);
    }

    return () => {
      if (autoScrollRef.current) {
        clearInterval(autoScrollRef.current);
      }
    };
  }, [isAutoScroll, currentIndex]);

  const goToNext = useCallback(() => {
    if (isTransitioning || currentIndex >= videoList.length - 1) return;
    setIsTransitioning(true);
    setSlideDirection('up');
    setIsPlaying(true);

    setTimeout(() => {
      setCurrentIndex(prev => Math.min(prev + 1, videoList.length - 1));
      setSlideDirection(null);
      setIsTransitioning(false);
    }, 300);
  }, [isTransitioning, currentIndex, videoList.length]);

  const goToPrev = useCallback(() => {
    if (isTransitioning || currentIndex <= 0) return;
    setIsTransitioning(true);
    setSlideDirection('down');
    setIsPlaying(true);

    setTimeout(() => {
      setCurrentIndex(prev => Math.max(prev - 1, 0));
      setSlideDirection(null);
      setIsTransitioning(false);
    }, 300);
  }, [isTransitioning, currentIndex]);

  const handleTouchStart = (e: React.TouchEvent) => {
    setTouchStart(e.touches[0].clientY);
  };

  const handleTouchEnd = (e: React.TouchEvent) => {
    if (isTransitioning) return;
    const delta = touchStart - e.changedTouches[0].clientY;
    if (Math.abs(delta) > 80) {
      if (delta > 0) {
        goToNext();
      } else {
        goToPrev();
      }
    }
  };

  const handleVideoClick = () => {
    if (!videoRef.current || isTransitioning) return;
    if (videoRef.current.paused) {
      videoRef.current.play();
      setIsPlaying(true);
    } else {
      videoRef.current.pause();
      setIsPlaying(false);
    }
  };

  const handleSeek = (e: React.MouseEvent<HTMLDivElement> | React.TouchEvent<HTMLDivElement>) => {
    if (!videoRef.current || !duration) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX;
    const percent = (clientX - rect.left) / rect.width;
    videoRef.current.currentTime = percent * duration;
  };

  const handleVideoEnded = () => {
    setIsPlaying(false);
    setIsAutoScroll(true); // Auto-scroll to next when video ends
    setTimeout(() => {
      setIsPlaying(true);
      videoRef.current?.play();
    }, 500);
  };

  const handleTimeUpdate = () => {
    if (videoRef.current) setCurrentTime(videoRef.current.currentTime);
  };

  const handleLoadedMetadata = () => {
    if (videoRef.current) setDuration(videoRef.current.duration);
  };

  const toggleFavorite = () => {
    if (currentVideo) onToggleFavorite(currentVideo);
  };

  const toggleMute = () => {
    const newMuted = !isMuted;
    setIsMuted(newMuted);
    if (videoRef.current) {
      videoRef.current.muted = newMuted;
    }
  };

  const toggleAutoScroll = () => {
    setIsAutoScroll(!isAutoScroll);
  };

  const getTransformStyle = () => {
    if (!slideDirection) return 'translateY(0)';
    if (slideDirection === 'up') return 'translateY(-100%)';
    return 'translateY(100%)';
  };

  return (
    <div
      ref={containerRef}
      className="fixed inset-0 z-50 bg-black select-none"
      onTouchStart={handleTouchStart}
      onTouchEnd={handleTouchEnd}
    >
      {/* Back button */}
      <button
        onClick={onClose}
        className="absolute top-4 left-4 z-50 bg-black/50 hover:bg-black/70 rounded-full p-2 transition-all backdrop-blur-sm"
      >
        <ArrowLeft className="w-6 h-6 text-white" />
      </button>

      {/* Video container */}
      <div
        className="absolute inset-0 transition-transform duration-300 ease-out will-change-transform"
        style={{ transform: getTransformStyle() }}
      >
        {currentVideo && (
          <video
            ref={videoRef}
            className="w-full h-full object-contain bg-black"
            loop
            muted={isMuted}
            playsInline
            onClick={handleVideoClick}
            onEnded={handleVideoEnded}
            onWaiting={() => setIsPlaying(false)}
            onPlaying={() => setIsPlaying(true)}
            onTimeUpdate={handleTimeUpdate}
            onLoadedMetadata={handleLoadedMetadata}
          />
        )}
        {/* Hidden preload video */}
        <video
          ref={preloadRef}
          className="hidden"
          muted
          playsInline
        />
      </div>

      {/* App name at top */}
      <div className="absolute top-4 left-1/2 -translate-x-1/2 z-50">
        <h1 className="text-xl font-bold tracking-tight">
          <span className="text-white">Desi</span>
          <span className="text-red-600">Netflix</span>
        </h1>
      </div>

      {/* Play indicator */}
      {!isPlaying && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="bg-black/50 backdrop-blur-sm rounded-full p-6">
            <Play className="w-16 h-16 text-white fill-white" />
          </div>
        </div>
      )}

      {/* Side controls - middle right, vertically centered */}
      <div className="absolute right-2 top-1/2 -translate-y-1/2 flex flex-col gap-2 z-40">
        <button
          onClick={toggleMute}
          className="bg-black/50 backdrop-blur-sm rounded-full p-2 hover:bg-black/70 transition-colors"
        >
          {isMuted ? (
            <VolumeX className="w-5 h-5 text-white" />
          ) : (
            <Volume2 className="w-5 h-5 text-white" />
          )}
        </button>

        <button
          onClick={toggleFavorite}
          className={`rounded-full p-2 transition-colors ${
            isFavorite ? 'bg-red-600' : 'bg-black/50 hover:bg-black/70 backdrop-blur-sm'
          }`}
        >
          <Heart className={`w-5 h-5 ${isFavorite ? 'fill-white text-white' : 'text-white'}`} />
        </button>

        <button
          onClick={onShowFavorites}
          className="bg-black/50 backdrop-blur-sm rounded-full p-2 hover:bg-black/70 transition-colors relative"
        >
          <Bookmark className="w-5 h-5 text-white" />
          {favorites.length > 0 && (
            <span className="absolute -top-1 -right-1 bg-red-600 text-white text-xs w-4 h-4 rounded-full flex items-center justify-center">
              {favorites.length}
            </span>
          )}
        </button>

        <button
          onClick={toggleAutoScroll}
          className={`rounded-full p-2 transition-colors ${
            isAutoScroll ? 'bg-red-600' : 'bg-black/50 hover:bg-black/70 backdrop-blur-sm'
          }`}
        >
          <Instagram className="w-5 h-5 text-white" />
        </button>
      </div>

      {/* Seekbar - thin and at bottom, z-index below buttons */}
      <div className="absolute bottom-0 left-0 right-0 p-3 z-30">
        <div
          className="relative h-1 bg-gray-600 rounded-full cursor-pointer"
          onClick={handleSeek}
          onTouchStart={handleSeek}
        >
          <div
            className="absolute top-0 left-0 h-full bg-red-600 rounded-full"
            style={{ width: `${duration > 0 ? (currentTime / duration) * 100 : 0}%` }}
          />
        </div>
      </div>

      {/* Bottom info - only title and progress */}
      <div className="absolute bottom-2 left-4 right-16 z-30">
        <p className="text-white text-sm font-semibold truncate">{currentVideo?.title}</p>
        <div className="flex items-center gap-2 mt-1">
          <span className="text-gray-400 text-xs">
            {currentIndex + 1} / {videoList.length}
          </span>
          <span className="text-gray-400 text-xs">
            {formatTime(currentTime)} / {formatTime(duration)}
          </span>
        </div>
      </div>
    </div>
  );
}

// Standard Video Player
function VideoPlayer({ video, onClose }: {
  video: Video;
  onClose: () => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isMuted, setIsMuted] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showControls, setShowControls] = useState(true);
  const hideControlsTimer = useRef<NodeJS.Timeout>();

  const resetHideTimer = () => {
    setShowControls(true);
    if (hideControlsTimer.current) clearTimeout(hideControlsTimer.current);
    hideControlsTimer.current = setTimeout(() => {
      if (isPlaying) setShowControls(false);
    }, 3000);
  };

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleEsc);
    return () => document.removeEventListener('keydown', handleEsc);
  }, [onClose]);

  useEffect(() => {
    if (isPlaying) resetHideTimer();
  }, [isPlaying]);

  const togglePlay = () => {
    if (!videoRef.current) return;
    if (isPlaying) videoRef.current.pause();
    else videoRef.current.play();
  };

  const handleTimeUpdate = () => {
    if (videoRef.current) setCurrentTime(videoRef.current.currentTime);
  };

  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      setDuration(videoRef.current.duration);
      setIsLoading(false);
    }
  };

  const handleCanPlay = () => {
    setIsLoading(false);
    if (videoRef.current) {
      videoRef.current.play();
      setIsPlaying(true);
    }
  };

  const handleError = () => {
    setError('Failed to load video.');
    setIsLoading(false);
  };

  const handleSeek = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!videoRef.current || !duration) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const percent = (e.clientX - rect.left) / rect.width;
    videoRef.current.currentTime = percent * duration;
  };

  const toggleMute = () => {
    if (videoRef.current) {
      videoRef.current.muted = !isMuted;
      setIsMuted(!isMuted);
    }
  };

  const toggleFullscreen = async () => {
    if (!containerRef.current) return;
    if (!document.fullscreenElement) {
      await containerRef.current.requestFullscreen();
    } else {
      await document.exitFullscreen();
    }
  };

  const skip = (seconds: number) => {
    if (videoRef.current) videoRef.current.currentTime += seconds;
  };

  const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div
      ref={containerRef}
      className="fixed inset-0 z-50 bg-black flex items-center justify-center"
      onMouseMove={resetHideTimer}
    >
      <button
        onClick={onClose}
        className="absolute top-4 right-4 z-50 bg-black/50 hover:bg-black/70 rounded-full p-2"
      >
        <X className="w-8 h-8 text-white" />
      </button>

      <video
        ref={videoRef}
        src={video.url}
        className="w-full h-full object-contain"
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleLoadedMetadata}
        onCanPlay={handleCanPlay}
        onError={handleError}
        onWaiting={() => setIsLoading(true)}
        onPlaying={() => { setIsLoading(false); setIsPlaying(true); }}
        onPause={() => setIsPlaying(false)}
        onClick={togglePlay}
        playsInline
      />

      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/50">
          <div className="w-16 h-16 border-4 border-gray-600 border-t-red-600 rounded-full animate-spin" />
        </div>
      )}

      {error && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/80">
          <p className="text-red-500 text-xl mb-4">{error}</p>
          <button
            onClick={() => { setError(null); setIsLoading(true); videoRef.current?.load(); }}
            className="bg-red-600 text-white px-6 py-2 rounded-md"
          >
            Retry
          </button>
        </div>
      )}

      {!isPlaying && !isLoading && !error && (
        <button onClick={togglePlay} className="absolute inset-0 flex items-center justify-center bg-black/30">
          <div className="bg-red-600 rounded-full p-6">
            <Play className="w-16 h-16 text-white fill-white" />
          </div>
        </button>
      )}

      <div className={`absolute bottom-0 left-0 right-0 transition-opacity ${showControls ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}>
        <div className="h-1 bg-gray-700 cursor-pointer group" onClick={handleSeek}>
          <div className="h-full bg-red-600" style={{ width: `${progress}%` }} />
        </div>
        <div className="bg-gradient-to-t from-black to-transparent p-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button onClick={togglePlay}>
              {isPlaying ? (
                <svg className="w-8 h-8 text-white" viewBox="0 0 24 24" fill="currentColor">
                  <rect x="6" y="4" width="4" height="16" />
                  <rect x="14" y="4" width="4" height="16" />
                </svg>
              ) : (
                <Play className="w-8 h-8 text-white fill-white" />
              )}
            </button>
            <button onClick={() => skip(-10)} className="text-white"><SkipBack className="w-6 h-6" /></button>
            <button onClick={() => skip(10)} className="text-white"><SkipForward className="w-6 h-6" /></button>
            <button onClick={toggleMute} className="text-white">
              {isMuted ? <VolumeX className="w-6 h-6" /> : <Volume2 className="w-6 h-6" />}
            </button>
            <span className="text-gray-300 text-sm">{formatTime(currentTime)} / {formatTime(duration)}</span>
          </div>
          <button onClick={toggleFullscreen} className="text-white"><Maximize className="w-6 h-6" /></button>
        </div>
      </div>

      <div className="absolute top-0 left-0 right-0 p-4 bg-gradient-to-b from-black/80 to-transparent">
        <h2 className="text-xl text-white font-bold truncate">{video.title}</h2>
        <p className="text-gray-400 text-sm">{video.category}</p>
      </div>
    </div>
  );
}

function VideoCard({ video, onPlay, onToggleFavorite, isFavorite }: {
  video: Video;
  onPlay: (video: Video) => void;
  onToggleFavorite?: (video: Video) => void;
  isFavorite?: boolean;
}) {
  const [isLoaded, setIsLoaded] = useState(false);

  const handleFavoriteClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (onToggleFavorite) onToggleFavorite(video);
  };

  return (
    <div
      className="flex-shrink-0 w-48 md:w-56 mr-4 cursor-pointer group relative overflow-hidden rounded-md transition-all duration-300 hover:scale-105"
      onClick={() => onPlay(video)}
    >
      <div className="aspect-video bg-gray-800 relative">
        {!isLoaded && <div className="absolute inset-0 animate-pulse bg-gray-700" />}
        <img
          src={video.thumbnail}
          alt={video.title}
          className={`w-full h-full object-cover transition-opacity ${isLoaded ? 'opacity-100' : 'opacity-0'}`}
          onLoad={() => setIsLoaded(true)}
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent opacity-0 group-hover:opacity-100 flex items-center justify-center">
          <div className="bg-red-600 rounded-full p-3">
            <Play className="w-6 h-6 text-white fill-white" />
          </div>
        </div>
        {/* Favorite button */}
        {onToggleFavorite && (
          <button
            onClick={handleFavoriteClick}
            className="absolute top-2 right-2 bg-black/50 rounded-full p-1.5 hover:bg-black/70 transition-colors z-10"
          >
            <Heart className={`w-4 h-4 ${isFavorite ? 'fill-red-500 text-red-500' : 'text-white'}`} />
          </button>
        )}
        <div className="absolute bottom-0 left-0 right-0 p-2 bg-gradient-to-t from-black/90">
          <p className="text-xs text-gray-200 line-clamp-2">{video.title}</p>
        </div>
      </div>
    </div>
  );
}

function VideoCarousel({ category, onPlay, favorites, onToggleFavorite }: {
  category: CategoryVideos;
  onPlay: (video: Video) => void;
  favorites?: Video[];
  onToggleFavorite?: (video: Video) => void;
}) {
  const [emblaRef, emblaApi] = useEmblaCarousel({ align: 'start', loop: false, skipSnaps: true });

  const scrollPrev = useCallback(() => emblaApi && emblaApi.scrollPrev(), [emblaApi]);
  const scrollNext = useCallback(() => emblaApi && emblaApi.scrollNext(), [emblaApi]);

  return (
    <div className="relative group mb-8">
      <h2 className="text-xl md:text-2xl font-bold text-white mb-4 px-4 md:px-16">{category.name}</h2>
      <div className="relative">
        <button onClick={scrollPrev} className="absolute left-0 top-0 bottom-12 z-10 bg-black/80 p-2 opacity-0 group-hover:opacity-100">
          <ChevronLeft className="w-8 h-8 text-white" />
        </button>
        <div className="overflow-hidden px-4 md:px-16" ref={emblaRef}>
          <div className="flex">
            {category.videos.slice(0, 50).map((video) => (
              <VideoCard
                key={video.id}
                video={video}
                onPlay={onPlay}
                onToggleFavorite={onToggleFavorite}
                isFavorite={favorites?.some(v => v.id === video.id)}
              />
            ))}
          </div>
        </div>
        <button onClick={scrollNext} className="absolute right-0 top-0 bottom-12 z-10 bg-black/80 p-2 opacity-0 group-hover:opacity-100">
          <ChevronRight className="w-8 h-8 text-white" />
        </button>
      </div>
    </div>
  );
}

function HeroSection({ videos, onPlay }: { videos: Video[]; onPlay: (video: Video) => void }) {
  const [current, setCurrent] = useState(0);
  const video = videos[current];

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrent((c) => (c + 1) % videos.length);
    }, 6000);
    return () => clearInterval(timer);
  }, [videos.length]);

  if (!video) return null;

  return (
    <div className="relative h-96 md:h-[500px] overflow-hidden">
      <div className="absolute inset-0">
        <img src={video.thumbnail} alt={video.title} className="w-full h-full object-cover" />
      </div>
      <div className="absolute inset-0 bg-gradient-to-r from-black via-black/50 to-transparent" />
      <div className="absolute inset-0 bg-gradient-to-t from-[#141414] via-transparent to-transparent" />
      <div className="relative h-full flex flex-col justify-center px-4 md:px-16 max-w-2xl">
        <h1 className="text-3xl md:text-5xl font-bold text-white mb-4 leading-tight">{video.title}</h1>
        <div className="flex gap-3">
          <button
            onClick={() => onPlay(video)}
            className="flex items-center gap-2 bg-white text-black px-6 py-3 rounded-md font-semibold hover:bg-gray-200"
          >
            <Play className="w-5 h-5 fill-current" /> Play
          </button>
          <button className="flex items-center gap-2 bg-gray-600/70 text-white px-6 py-3 rounded-md font-semibold">
            <Flame className="w-5 h-5" /> More Info
          </button>
        </div>
      </div>
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 flex gap-2">
        {videos.slice(0, 5).map((_, i) => (
          <button key={i} onClick={() => setCurrent(i)} className={`w-2 h-2 rounded-full ${i === current ? 'bg-white' : 'bg-gray-500'}`} />
        ))}
      </div>
    </div>
  );
}

export default function App() {
  const [categories, setCategories] = useState<CategoryVideos[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedVideo, setSelectedVideo] = useState<Video | null>(null);
  const [showTikTok, setShowTikTok] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<Video[]>([]);
  const [showSearch, setShowSearch] = useState(false);
  const [favorites, setFavorites] = useState<Video[]>(() => {
    // Load favorites from localStorage on init
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('netflix-favorites');
      return saved ? JSON.parse(saved) : [];
    }
    return [];
  });
  const [showFavoritesPage, setShowFavoritesPage] = useState(false);
  const [tiktokStartVideo, setTiktokStartVideo] = useState<Video | null>(null);

  // Save favorites to localStorage whenever they change
  useEffect(() => {
    localStorage.setItem('netflix-favorites', JSON.stringify(favorites));
  }, [favorites]);

  useEffect(() => {
    parseM3U(M3U_URL).then((data) => {
      setCategories(data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (searchQuery.trim()) {
      const allVideos = categories.flatMap((c) => c.videos);
      setSearchResults(filterVideosBySearch(allVideos, searchQuery));
    } else {
      setSearchResults([]);
    }
  }, [searchQuery, categories]);

  const toggleFavorite = (video: Video) => {
    setFavorites(prev => {
      const exists = prev.some(v => v.id === video.id);
      if (exists) {
        return prev.filter(v => v.id !== video.id);
      } else {
        return [video, ...prev]; // Add newest first
      }
    });
  };

  const openTikTok = (video?: Video) => {
    setTiktokStartVideo(video || null);
    setShowTikTok(true);
  };

  const allVideos = categories.flatMap((c) => c.videos);
  const desiTalesVideos = categories.find((c) => c.name === 'DesiTales')?.videos || [];

  return (
    <div className="min-h-screen bg-[#141414]">
      {/* Header */}
      <header className="fixed top-0 left-0 right-0 z-40 bg-gradient-to-b from-black/90 to-transparent p-4">
        <div className="flex items-center justify-between max-w-7xl mx-auto">
          <div className="flex items-center gap-8">
            <h1 className="text-3xl font-bold text-red-600 tracking-tight">FEED</h1>
            <nav className="hidden md:flex items-center gap-6">
              <a href="#" className="text-gray-300 hover:text-white flex items-center gap-2">
                <Home className="w-4 h-4" /> Home
              </a>
              <a href="#" className="text-gray-300 hover:text-white flex items-center gap-2">
                <Clock className="w-4 h-4" /> Recent
              </a>
              <a href="#" className="text-gray-300 hover:text-white flex items-center gap-2">
                <Flame className="w-4 h-4" /> Trending
              </a>
            </nav>
          </div>
          <div className="flex items-center gap-4">
            <button
              onClick={() => setShowFavoritesPage(true)}
              className="text-gray-300 hover:text-white flex items-center gap-2 relative"
            >
              <Heart className="w-6 h-6" />
              {favorites.length > 0 && (
                <span className="absolute -top-1 -right-1 bg-red-600 text-white text-xs w-4 h-4 rounded-full flex items-center justify-center">
                  {favorites.length}
                </span>
              )}
            </button>
            <button
              onClick={() => openTikTok()}
              className="text-gray-300 hover:text-white flex items-center gap-2"
            >
              <Instagram className="w-6 h-6" />
              <span className="hidden md:inline">Reels</span>
            </button>
            <button onClick={() => setShowSearch(!showSearch)} className="text-gray-300 hover:text-white">
              <Search className="w-6 h-6" />
            </button>
          </div>
        </div>
      </header>

      {/* Search Bar */}
      {showSearch && (
        <div className="fixed top-16 left-0 right-0 z-40 bg-[#141414] px-4 py-4">
          <div className="max-w-3xl mx-auto">
            <div className="relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
              <input
                type="text"
                placeholder="Search videos..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-gray-800 text-white pl-12 pr-4 py-3 rounded-md focus:outline-none focus:ring-2 focus:ring-red-600"
                autoFocus
              />
            </div>
            {searchResults.length > 0 && (
              <div className="mt-4 grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
                {searchResults.slice(0, 12).map((video) => (
                  <div
                    key={video.id}
                    className="cursor-pointer"
                    onClick={() => { setSelectedVideo(video); setShowSearch(false); setSearchQuery(''); }}
                  >
                    <div className="aspect-video bg-gray-800 rounded-md overflow-hidden">
                      <img src={video.thumbnail} alt={video.title} className="w-full h-full object-cover hover:scale-105" />
                    </div>
                    <p className="text-xs text-gray-300 mt-2 line-clamp-2">{video.title}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center min-h-screen">
          <div className="animate-spin rounded-full h-16 w-16 border-t-4 border-red-600" />
        </div>
      ) : (
        <>
          <HeroSection videos={allVideos.slice(0, 10)} onPlay={setSelectedVideo} />
          <main className="relative z-10 pb-16">
            {categories.map((category) => (
              <VideoCarousel
                key={category.name}
                category={category}
                onPlay={setSelectedVideo}
                favorites={favorites}
                onToggleFavorite={toggleFavorite}
              />
            ))}
          </main>
          <footer className="bg-black py-12">
            <p className="text-gray-500 text-center">
              Powered by GitHub Auto-Feed | {allVideos.length} videos from 4 sources
            </p>
          </footer>
        </>
      )}

      {/* Video Player Modal */}
      {selectedVideo && (
        <VideoPlayer video={selectedVideo} onClose={() => setSelectedVideo(null)} />
      )}

      {/* Favorites Grid Page */}
      {showFavoritesPage && (
        <div className="fixed inset-0 z-50 bg-[#141414]">
          <header className="fixed top-0 left-0 right-0 z-40 bg-black/90 p-4 flex items-center gap-4">
            <button
              onClick={() => setShowFavoritesPage(false)}
              className="text-white p-2 hover:bg-white/10 rounded-full"
            >
              <ArrowLeft className="w-6 h-6" />
            </button>
            <h1 className="text-xl font-bold text-white">My Favorites</h1>
            <span className="text-gray-400 text-sm">{favorites.length} videos</span>
          </header>
          <main className="pt-20 pb-8 px-4">
            {favorites.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-[60vh] text-gray-400">
                <Heart className="w-16 h-16 mb-4" />
                <p>No favorites yet</p>
                <p className="text-sm mt-2">Tap the heart icon on videos to save them</p>
              </div>
            ) : (
              <div className="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2 md:gap-4">
                {favorites.map((video) => (
                  <div
                    key={video.id}
                    className="cursor-pointer group relative overflow-hidden rounded-md"
                    onClick={() => openTikTok(video)}
                  >
                    <div className="aspect-video bg-gray-800">
                      <img
                        src={video.thumbnail}
                        alt={video.title}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                      />
                    </div>
                    <button
                      onClick={(e) => { e.stopPropagation(); toggleFavorite(video); }}
                      className="absolute top-2 right-2 bg-black/50 rounded-full p-1.5 hover:bg-black/70 transition-colors z-10"
                    >
                      <Heart className="w-4 h-4 fill-red-500 text-red-500" />
                    </button>
                    <div className="absolute inset-0 bg-black/30 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
                      <div className="bg-red-600 rounded-full p-2">
                        <Play className="w-5 h-5 text-white fill-white" />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </main>
        </div>
      )}

      {/* TikTok-style Reels Player */}
      {showTikTok && (desiTalesVideos.length > 0 || favorites.length > 0) && (
        <TikTokPlayer
          videos={desiTalesVideos}
          onClose={() => { setShowTikTok(false); setTiktokStartVideo(null); }}
          favorites={favorites}
          onToggleFavorite={toggleFavorite}
          onShowFavorites={() => setShowFavoritesPage(true)}
          startVideo={tiktokStartVideo}
        />
      )}
    </div>
  );
}