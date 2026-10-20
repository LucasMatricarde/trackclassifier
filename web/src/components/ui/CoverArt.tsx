import { useEffect, useState } from "react";
import { getCoverUrl, getThumbUrl } from "../../api/client";

interface CoverArtProps {
  sha1: string;
  size: number;
  radius?: number;
}

/**
 * Capa com cantos arredondados.
 * Em web basta CSS border-radius + overflow:hidden — não precisa de canvas clip.
 */
export function CoverArt({ sha1, size, radius = 6 }: CoverArtProps) {
  const [src, setSrc] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    setSrc(getThumbUrl(sha1));
    setError(false);
  }, [sha1]);

  const handleError = () => {
    // Fallback para capa original
    if (!error) {
      setError(true);
      setSrc(getCoverUrl(sha1));
    } else {
      setSrc(null);
    }
  };

  if (!src) return null;

  return (
    <div
      className="cover-art"
      style={{ width: size, height: size, borderRadius: radius }}
    >
      <img
        src={src}
        alt=""
        width={size}
        height={size}
        onError={handleError}
        style={{ objectFit: "cover", width: "100%", height: "100%" }}
      />
    </div>
  );
}
